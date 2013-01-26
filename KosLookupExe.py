import cgi
import ctypes
import ctypes.wintypes
import datetime
import io
import os
import shutil
import sys
import tempfile
import time
import urllib
import urllib2
import webbrowser
import wx
import zipfile

import wx
import wx.html

try:
  import winsound
except ImportError:
  winsound = None

import ChatKosLookup


MINUS_TAG = u'[\u2212]'  # Unicode MINUS SIGN
KILLBOARD = "http://zkillboard.com/character/{}/"


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
    self.status_bar = self.CreateStatusBar(1)
    self.status_bar.PushStatusText("Starting...")
    self.SetSize((300, 800))
    self.SetBackgroundColour('white')
    self.recent_lines = []
    self.CreateMenu()
    self.UpdateLabels()
    self.KosCheckerPoll()
    self.CheckArgs()
    self.Show()

  def CreateMenu(self):
    file_menu = wx.Menu()
    help_menu = wx.Menu()
    reset_id = wx.NewId()
    update_id = wx.NewId()
    help_menu.Append(wx.ID_ABOUT, "About")
    file_menu.Append(reset_id, "Reset")
    file_menu.Append(update_id, "Update")
    file_menu.Append(wx.ID_EXIT, "Exit")
    menu_bar = wx.MenuBar()
    menu_bar.Append(file_menu, "File")
    menu_bar.Append(help_menu, "Help")
    self.SetMenuBar(menu_bar)
    self.Bind(wx.EVT_MENU, self.OnReset, id=reset_id)
    self.Bind(wx.EVT_MENU, self.OnUpdate, id=update_id)
    self.Bind(wx.EVT_MENU, self.OnExit, id=wx.ID_EXIT)
    self.Bind(wx.EVT_MENU, self.OnAbout, id=wx.ID_ABOUT)

  def UpdateIcon(self):
    """
    If running from py2exe, then the icon is implicitly obtained from the .exe
    file, but when running from source, this method pulls it in from the
    directory containing the python modules.
    """
    if sys.argv[0].endswith('.exe'):
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
    self.status_bar.PushStatusText("Checking for KOS pilots")
    for entry in iter(self.tailer.poll, None):
      action = True
      if entry.linekey in self.recent_lines:
        continue
      self.recent_lines.append(entry.linekey)

      self.status_bar.PushStatusText("KOS Checking {} pilots".format(
        len(entry.pilots)))
      kos, not_kos, error = self.checker.koscheck_logentry(entry.pilots)
      self.status_bar.PopStatusText()

      new_labels = []
      if entry.comment:
        new_labels.append(entry.comment)
      if kos or not_kos:
        new_labels.append('KOS: {}  Not KOS: {}'.format(len(kos), len(not_kos)))
      if kos:
        play_sound = True
        new_labels.extend(
            [(u'<font color="red">{minus} <a href="{killboard}">{pilot}</a> ({reason})</font>'.format(
                minus=MINUS_TAG,
                killboard=KILLBOARD.format(cid),
                kospath="http://kos.cva-eve.org/?q=" + urllib.quote(p),
                pilot=cgi.escape(p),
                reason=cgi.escape(reason)))
             for (p, reason, cid) in kos])
      if not_kos:
        if kos:
          new_labels.append('')
        new_labels.extend([('<font color="blue">[+] <a href="{killboard}">{pilot}</a></font>'.format(
                pilot=p, killboard=KILLBOARD.format(cid)))
                for (p, cid) in not_kos])
      if error:
        new_labels.append('Error: {}'.format(len(error)))
        new_labels.extend(error)
      if new_labels:
        new_labels.append('<hr>')
      self.labels = new_labels + self.labels
      self.labels = self.labels[:100]
    self.status_bar.PopStatusText()

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
    self.status_bar.PopStatusText()
    last_update = self.tailer.last_update()
    if last_update:
      status = "Last update: {}".format(
          datetime.datetime.fromtimestamp(last_update
            ).strftime("%Y-%m-%d %H:%M:%S"))
    else:
      status = "No logs found"
    self.status_bar.PushStatusText(status)
    self.html.SetPage('<br>'.join(self.labels))

  def UpdateTitle(self):
    self.SetLabel("Kill On Sight")

  def OnReset(self, event):
    logs_dir = GetEveLogsDir()
    self.tailer = ChatKosLookup.DirectoryTailer(logs_dir)
    last_update = self.tailer.last_update()
    self.labels = []
    self.labels.append('Checking logs in {}'.format(logs_dir))
    if last_update:
      minutes_ago = int((time.time() - last_update) / 60)
      last_update = datetime.datetime.fromtimestamp(last_update
            ).strftime("%Y-%m-%d %H:%M:%S")
      self.labels.append(
          'Reset Complete: reading {} log files'.format(
              len(self.tailer.watchers)))
      self.labels.append('last update: {}, {} minutes ago'.format(
              last_update, minutes_ago))
    else:
      self.labels.append(
          'Reset Complete, no log files found')
    self.UpdateLabels()

  def OnAbout(self, event):
    dlg = wx.MessageDialog(
        self,
        "KOS Lookup\nSee http://nrds.eu/\n"
        "Version: 0.8.1",
        'About',
        wx.OK | wx.ICON_INFORMATION)
    dlg.ShowModal()
    dlg.Destroy()

  def OnExit(self, event):
    self.Close()

  def CheckArgs(self):
    if not zipfile.is_zipfile(sys.executable):
      return

    if '/updated' in sys.argv:
      for x in range(10):
        try:
          if os.path.exists(sys.argv[2]):
            os.unlink(sys.argv[2])
        except OSError:
          time.sleep(.1)
      dlg = wx.MessageDialog(self, "Updates Complete", 'KosUpdater', wx.OK | wx.ICON_INFORMATION)
      dlg.ShowModal()
      dlg.Destroy()
      return

    if '/update' in sys.argv:
      realname = sys.argv[2]
      while 1:
        try:
          shutil.copy(sys.executable, sys.argv[2])
          break
        except WindowsError as e:
          time.sleep(.05)
      wx.Execute('"{}" /updated "{}"'.format(realname, sys.executable))
      sys.exit()
      return

  def OnUpdate(self, event):
    if not zipfile.is_zipfile(sys.executable):
      return

    files = self.CheckForUpdate()

    with zipfile.PyZipFile(sys.executable, 'r') as z:
      namelist = set(z.namelist())
      edit = False
      for filename, contents in list(files):
        if filename not in namelist:
          edit = True
        elif z.read(filename) != contents:
          edit = True
        else:
          files.remove((filename, contents))
      if not edit:
        dlg = wx.MessageDialog(self, "No Updates Found", 'KosUpdater', wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()
        return

    with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as tmpfile:
      shutil.copy(sys.executable, tmpfile.name)
    with zipfile.PyZipFile(tmpfile.name, 'a', compression=zipfile.ZIP_DEFLATED) as z:
      for zinfo in list(z.filelist):
        for name, contents in files:
          if zinfo.filename.startswith(name):
            z.filelist.remove(zinfo)
      for filename, contents in files:
        if filename not in namelist or z.read(filename) != contents:
          z.writestr(filename, contents)

    wx.Execute('"{}" /update "{}"'.format(tmpfile.name, sys.executable))
    sys.exit()

  def CheckForUpdate(self):
    """
    Will attempt to download the latest update from http://www.nrds.eu/

    The update is served from http://www.nrds.eu/download/update.zip and
    contains one or more python files, which will replace the files inside the 
    py2exe release.
    """
    try:
      f = urllib2.urlopen('http://www.nrds.eu/downloads/update.zip')
      update_zip = io.BytesIO(f.read())
      z = zipfile.ZipFile(update_zip, 'r')
    except Exception as e:
      dlg = wx.MessageDialog(
          self, 'Error retreiving update: {}'.format(e),
          'KosUpdater', wx.OK | wx.ICON_INFORMATION)
      dlg.ShowModal()
      dlg.Destroy()
      return []

    return [(filename, z.read(filename)) for filename in z.namelist()]


def main():
  app = wx.App(redirect=False)
  frame = MainFrame(None, -1, 'KOS Checker')
  app.MainLoop()


if __name__ == '__main__':
  main()
