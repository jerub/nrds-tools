import cgi
import ctypes
import ctypes.wintypes
import datetime
import os
import sys
import urllib
import webbrowser

import wx
import wx.html

try:
  import winsound
except ImportError:
  winsound = None

import ChatKosLookup


DIVIDER = '-' * 40
PLUS_TAG = '[+]'
MINUS_TAG = u'[\u2212]'  # Unicode MINUS SIGN


# Cargo-culted from:
# http://stackoverflow.com/questions/3927259/how-do-you-get-the-exact-path-to-my-documents
def GetMyDocumentsDir():
  shell32 = ctypes.windll.shell32
  buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH + 1)
  if shell32.SHGetSpecialFolderPathW(None, buf, 0x5, False):
    return buf.value
  return None


def GetEveLogsDir():
  home = GetMyDocumentsDir()
  if not home:
    return None
  if os.path.isdir(os.path.join(home, 'EVE', 'logs', 'Chatlogs')):
    return os.path.join(home, 'EVE', 'logs', 'Chatlogs')
  if os.path.isdir(os.path.join(home, 'CCP', 'EVE', 'logs', 'Chatlogs')):
    return os.path.join(home, 'CCP', 'EVE', 'logs', 'Chatlogs')
  return None


class wxHTML(wx.html.HtmlWindow):
  def OnLinkClicked(self, link):
    webbrowser.open(link.GetHref())


class MainFrame(wx.Frame):
  def __init__(self, *args, **kwargs):
    wx.Frame.__init__(self, *args, **kwargs)
    self.UpdateIcon()
    self.UpdateTitle()
    self.checker = ChatKosLookup.KosChecker()
    self.tailer = ChatKosLookup.DirectoryTailer(GetEveLogsDir())
    self.labels = []
    self.html = wxHTML(self, style=wx.html.HW_SCROLLBAR_NEVER)
    self.SetSize((300, 800))
    self.SetBackgroundColour('white')
    self.Show()
    self.recent_lines = []
    self.KosCheckerPoll()

  def UpdateIcon(self):
    """
    If running from py2exe, then the icon is implicitly obtained from the .exe
    file, but when running from source, this method pulls it in from the
    directory containing the python modules.
    """
    try:
      loc = wx.IconLocation(sys.argv[0], 0)
      self.SetIcon(wx.IconFromLocation(loc))
      return
    except:
      pass

    try:
      icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
    except NameError:
      # __file__ does not exist
      return
    if os.path.exists(icon_path):
      self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))

  def KosCheckerPoll(self):
    play_sound = False
    action = False
    for entry in iter(self.tailer.poll, None):
      action = True
      if entry.linekey in self.recent_lines:
        continue
      self.recent_lines.append(entry.linekey)

      kos, not_kos, error = self.checker.koscheck_logentry(entry.pilots)
      new_labels = []
      if entry.comment:
        new_labels.append(entry.comment)
      if kos or not_kos:
        new_labels.append('KOS: %d  Not KOS: %d' % (len(kos), len(not_kos)))
      if kos:
        play_sound = True
        new_labels.extend(
            [(u'<font color="red">{minus} <a href="{kospath}">{pilot}</a> ({reason})</font>'.format(
                minus=MINUS_TAG,
                kospath="http://kos.cva-eve.org/?q=" + urllib.quote(p),
                pilot=cgi.escape(p),
                reason=cgi.escape(reason)))
             for (p, reason) in kos])
      if not_kos:
        if kos:
          new_labels.append('')
        new_labels.extend([('<font color="blue">%s %s</font>' % (PLUS_TAG, p)) for p in not_kos])
      if error:
        new_labels.append('Error: %d' % len(error))
        new_labels.extend(error)
      if new_labels:
        new_labels.append(DIVIDER)
      self.labels = new_labels + self.labels
      self.labels = self.labels[:100]

    if play_sound:
      self.PlayKosAlertSound()
    if action:
      self.recent_lines = self.recent_lines[-100:]
      self.UpdateLabels()
    wx.FutureCall(1000, self.KosCheckerPoll)

  def PlayKosAlertSound(self):
    global winsound
    if winsound:
      try:
        winsound.PlaySound("SystemQuestion", winsound.SND_ALIAS)
      except:
        # such as when there's no SystemQuestion sound, reported by some users.
        winsound = False

  def UpdateLabels(self):
    self.html.SetPage('<br>'.join(self.labels))

  def UpdateTitle(self):
    self.SetLabel("Kill On Sight")

if __name__ == '__main__':
  app = wx.App(redirect=False)
  frame = MainFrame(None, -1, 'KOS Checker')
  app.MainLoop()

