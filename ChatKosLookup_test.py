
import tempfile
import unittest
import os
import sys

sys.path.append('evelink-api')

import ChatKosLookup
from ChatKosLookup import Entry


class TestFileTailer(unittest.TestCase):
  def setUp(self):
    self.tmpfile = tempfile.mktemp()
    open(self.tmpfile, 'w').close()
    self.ft = ChatKosLookup.FileTailer(self.tmpfile)

  def test_check_nothing(self):
    line = "[ 2012.07.29 00:23:56 ] Foo Bar > nothing much"
    answer = self.ft.check(line)
    self.assertEquals(answer, None)

  def test_check_kos_xxx(self):
    answer = self.ft.check("[ 2012.07.29 00:23:56 ] Foo Bar > xxx Bad Pilot")
    self.assertEquals(answer,
        Entry(('Bad Pilot',), '[00:23:56] Foo Bar >',
			        (0, 23, 'Foo Bar', ('Bad Pilot',), None)))

  def test_check_kos_comment(self):
    answer = self.ft.check("[ 2012.07.29 00:23:56 ] Foo Bar > xxx Bad Pilot # 9uy")
    self.assertEquals(answer,
        Entry(('Bad Pilot',), '[00:23:56] Foo Bar > 9uy',
			        (0, 23, 'Foo Bar', ('Bad Pilot',), '9uy')))

  def test_check_kos_fff(self):
    answer = self.ft.check("[ 2012.07.29 00:23:56 ] Foo Bar > fff Bad Pilot")
    self.assertEquals(answer,
        Entry(('Bad Pilot',), '[00:23:56] Foo Bar >',
			        (0, 23, 'Foo Bar', ('Bad Pilot',), None)))

  def test_check_kos_gq(self):
    answer = self.ft.check("[ 2012.07.29 00:23:56 ] Foo Bar > xxx GQSmooth00")
    self.assertEquals(answer,
        Entry(('GQSmooth00',), '[00:23:56] Foo Bar >',
			        (0, 23, 'Foo Bar', ('GQSmooth00',), None)))

  def test_check_kos_obrian(self):
    answer = self.ft.check("[ 2012.07.29 00:23:56 ] O'Goode > xxx Bad O'brian")
    self.assertEquals(answer,
        Entry(('Bad O\'brian',), '[00:23:56] O\'Goode >',
			        (0, 23, 'O\'Goode', ('Bad O\'brian',), None)))

  def test_check_kos_ii(self):
    answer = self.ft.check("[ 2012.07.29 00:23:56 ] A -A > xxx I -I")
    self.assertEquals(answer,
        Entry(('I -I',), '[00:23:56] A -A >',
			        (0, 23, 'A -A', ('I -I',), None)))

  def tearDown(self):
    self.ft.close()
    os.unlink(self.tmpfile)


if __name__ == '__main__':
  unittest.main()
