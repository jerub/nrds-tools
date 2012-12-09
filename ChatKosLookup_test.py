
import tempfile
import unittest
import os
import sys

sys.path.append('evelink-api')

import ChatKosLookup


class TestFileTailer(unittest.TestCase):
  def setUp(self):
    self.tmpfile = tempfile.mktemp()
    open(self.tmpfile, 'w').close()

  def test_check_nothing(self):
    self.ft = ChatKosLookup.FileTailer(self.tmpfile)
    line = "[ 2012.07.29 00:23:56 ] Foo Bar > nothing much"
    answer = self.ft.check(line)
    self.assertEquals(answer, None)

  def test_check_kos_xxx(self):
    self.ft = ChatKosLookup.FileTailer(self.tmpfile)
    answer = self.ft.check("[ 2012.07.29 00:23:56 ] Foo Bar > xxx Bad Pilot")
    self.assertEquals(answer, (['Bad Pilot'], '[00:23:56] Foo Bar >'))

  def test_check_kos_comment(self):
    self.ft = ChatKosLookup.FileTailer(self.tmpfile)
    answer = self.ft.check("[ 2012.07.29 00:23:56 ] Foo Bar > xxx Bad Pilot # 9uy")
    self.assertEquals(answer, (['Bad Pilot'], '[00:23:56] Foo Bar > 9uy'))

  def test_check_kos_yyy(self):
    self.ft = ChatKosLookup.FileTailer(self.tmpfile)
    answer = self.ft.check("[ 2012.07.29 00:23:56 ] Foo Bar > xxx Bad Pilot")
    self.assertEquals(answer, (['Bad Pilot'], '[00:23:56] Foo Bar >'))

  def test_check_kos_gq(self):
    self.ft = ChatKosLookup.FileTailer(self.tmpfile)
    answer = self.ft.check("[ 2012.07.29 00:23:56 ] Foo Bar > xxx GQSmooth00")
    self.assertEquals(answer, (['GQSmooth00'], '[00:23:56] Foo Bar >'))

  def test_check_kos_obrian(self):
    self.ft = ChatKosLookup.FileTailer(self.tmpfile)
    answer = self.ft.check("[ 2012.07.29 00:23:56 ] O'Goode > xxx Bad O'brian")
    self.assertEquals(answer, (['Bad O\'brian'], '[00:23:56] O\'Goode >'))

  def tearDown(self):
    self.ft.close()
    os.unlink(self.tmpfile)


if __name__ == '__main__':
  unittest.main()
