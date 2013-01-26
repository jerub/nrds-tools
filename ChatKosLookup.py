#!/usr/bin/env python

"""Checks pilots mentioned in the EVE chatlogs against a KOS list."""

import codecs
import collections
import datetime
import operator
import re
from evelink import api, eve
from evelink.cache.sqlite import SqliteCache
import sys, os, tempfile, time, json, urllib2, urllib

KOS_CHECKER_URL = 'http://kos.cva-eve.org/api/?c=json&type=unit&%s'
NPC = 'npc'
LASTCORP = 'lastcorp'

Entry = collections.namedtuple('Entry', 'pilots comment linekey')

class FileTailer:
  MATCH = re.compile(
      # each line starts with a byte order marker
      u'\ufeff?'
      # [ date time ]
      ur'\[ (?P<date>\d+\.\d+\.\d+) (?P<time>\d+:\d+:\d+) \] '
      # Pilot Name >
      ur'(?P<pilot>[a-z0-9\'\-]+(?: [a-z0-9\'\-]+)?) > '
      # xxx or fff (any case), then the names of pilots
      ur'(?:xxx|fff) (?P<names>[a-z0-9\'\- \r\n]+)'
      # A hash then a comment
      ur'(?:#(?P<comment>.*))?',
      re.IGNORECASE)

  def __init__(self, filename, encoding='utf-16'):
    self.filename = filename
    self.handle = codecs.open(filename, 'rb', encoding)

    # seek to the end
    fstat = os.fstat(self.handle.fileno())
    self.handle.seek(fstat.st_size)
    self.mtime = fstat.st_mtime

  def close(self):
    self.handle.close()

  def poll(self):
    fstat = os.fstat(self.handle.fileno())
    size = fstat.st_size
    self.mtime = fstat.st_mtime
    where = self.handle.tell()
    while size > where:
      try:
        line = self.handle.readline()
      except UnicodeError:
        self.close()
        raise
      where = self.handle.tell()

      answer = self.check(line)
      if answer:
        return answer

    return None

  def last_update(self):
    return self.mtime

  def check(self, line):
    m = self.MATCH.match(line)
    if not m:
      return None

    logdate = m.group('date')
    logtime = m.group('time')
    timestamp = datetime.datetime.strptime(
        '{} {}'.format(logdate, logtime),
        '%Y.%m.%d %H:%M:%S')
    pilot = m.group('pilot')
    names = m.group('names').replace('  ', '\n')
    names = tuple(n.strip() for n in names.splitlines())
    if m.group('comment'):
      suffix = m.group('comment').strip()
      comment = '[%s] %s > %s' % (logtime, pilot, suffix)
    else:
      suffix = None
      comment = '[%s] %s >' % (logtime, pilot)

    linekey = (timestamp.hour, timestamp.minute, pilot, names, suffix)
    return Entry(names, comment, linekey)


class DirectoryTailer:
  def __init__(self, path):
    self.path = path
    self.watchers = {}
    self.mtime = 0

    for _answer in iter(self.poll, None):
      pass

  def last_update(self):
    if self.watchers:
      return max(w.last_update() for w in self.watchers.itervalues())
    else:
      return None

  def poll(self):
    st_mtime = os.stat(self.path).st_mtime
    if st_mtime != self.mtime:
      self.mtime = st_mtime
      for name in os.listdir(self.path):
        filename = os.path.join(self.path, name)
        if filename in self.watchers:
          continue
        # anything within a day.
        if abs(self.mtime - os.stat(filename).st_mtime) < 86400:
          self.watchers[filename] = FileTailer(filename)

    for filename, watcher in self.watchers.items():
      try:
        for answer in iter(watcher.poll, None):
          return answer
      except UnicodeError:
        del self.watchers[filename]
    return None


class KosChecker:
  """Maintains API state and performs KOS checks."""

  def __init__(self):
    # Set up caching.
    cache_file = os.path.join(tempfile.gettempdir(), 'koscheck')
    self.cache = SqliteCache(cache_file)

    self.api = api.API(cache=self.cache)
    self.eve = eve.EVE(api=self.api)

  def koscheck(self, player):
    """Checks a given player against the KOS list, including esoteric rules."""
    kos = self.koscheck_internal(player)
    cid = self.eve.character_id_from_name(player)
    if kos not in (None, NPC):
      return kos, cid

    # We were unable to find the player. Use employment history to
    # get their current corp and look that up. If it's an NPC corp,
    # we'll get bounced again.
    history = self.employment_history(cid)

    in_npc_corp = False
    for corp in history:
      kos = self.koscheck_internal(corp)
      if kos != NPC:
        break
      in_npc_corp = True

    if kos == NPC:
      kos = None

    if in_npc_corp and kos:
      kos = '%s: %s' % (LASTCORP, kos)

    return kos, cid

  def koscheck_internal(self, entity):
    """Looks up KOS entries by directly calling the CVA KOS API.

    @returns: The reason this pilot is KOS.
    """
    cache_key = self.api._cache_key(KOS_CHECKER_URL, {'entity': entity})

    result = self.cache.get(cache_key)
    if not result:
      result = json.load(urllib2.urlopen(
          KOS_CHECKER_URL % urllib.urlencode({'q' : entity})))
      self.cache.put(cache_key, result, 60*60)

    for value in result['results']:
      # Require exact match (case-insensitively).
      if value['label'].lower() != entity.lower():
        continue
      if value['type'] == 'alliance' and value['ticker'] == None:
        # Bogus alliance created instead of NPC corp.
        continue
      while value:
        if value['kos']:
          return '%s: %s' % (value['type'], value['label'])
        if 'npc' in value and value['npc']:
          # Signal that further lookup is needed of player's last corp
          return NPC

        if 'corp' in value:
          value = value['corp']
        elif 'alliance' in value:
          value = value['alliance']
        else:
          return

  def employment_history(self, cid):
    """Retrieves a player's most recent corporations via EVE api."""
    cdata = self.eve.character_info_from_id(cid)
    corps = cdata['history']
    unique_corps = []
    for corp in corps:
      if corp['corp_id'] not in unique_corps:
        unique_corps.append(corp['corp_id'])
    mapping = self.eve.character_names_from_ids(unique_corps)
    return [mapping[cid] for cid in unique_corps]

  def loop(self, filename, handler):
    """Performs KOS processing on each line read from the log file.

    handler is a function of 3 args: (kos, notkos, error) that is called
    every time there is a new KOS result.
    """
    tailer = FileTailer(filename)
    while True:
      entry, comment = tailer.poll()
      if not entry:
        time.sleep(1.0)
        continue
      kos, not_kos, error = self.koscheck_logentry(entry)
      handler(comment, kos, not_kos, error)

  def koscheck_logentry(self, entry):
    kos = []
    notkos = []
    error = []
    for person in entry:
      if person.isspace() or len(person) == 0:
        continue
      person = person.strip(' .')
      try:
        reason, cid = self.koscheck(person)
        if reason:
          kos.append((person, reason, cid))
        else:
          notkos.append((person, cid))
      except:
        error.append(person)
        raise
    kos.sort(key=operator.itemgetter(1, 0))
    return (kos, notkos, error)


def stdout_handler(comment, kos, notkos, error):
  fmt = '%s%6s (%3d) %s\033[0m'
  if comment:
    print comment
  print fmt % ('\033[31m', 'KOS', len(kos), len(kos) * '*')
  print fmt % ('\033[34m', 'NotKOS', len(notkos), len(notkos) * '*')
  if len(error) > 0:
    print fmt % ('\033[33m', 'Error', len(error), len(error) * '*')
  print
  for (person, reason) in kos:
    print u'\033[31m[\u2212] %s\033[0m (%s)' % (person, reason)
  print
  for person in notkos:
    print '\033[34m[+] %s\033[0m' % person
  print
  for person in error:
    print '\033[33m[?] %s\033[0m' % person
  print '-----'


if __name__ == '__main__':
  if len(sys.argv) > 1:
    KosChecker().loop(sys.argv[1], stdout_handler)
  else:
    print ('Usage: %s ~/EVE/logs/ChatLogs/Fleet_YYYYMMDD_HHMMSS.txt' %
           sys.argv[0])

