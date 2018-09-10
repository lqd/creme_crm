# -*- coding: utf-8 -*-

try:
    from datetime import datetime, date, timedelta
    from functools import partial
    from os.path import join
    import string

    from pytz import timezone

    from PIL.Image import open as open_img

    from django.conf import settings
    from django.http import Http404
    from django.urls import reverse
    from django.utils.timezone import is_naive, is_aware, override as override_tz, make_aware
    from django.utils.translation import ugettext_lazy

    from ..base import CremeTestCase
    from ..fake_models import FakeContact, FakeCivility

    # from creme.creme_core.models import PreferedMenuItem
    from creme.creme_core.global_info import clear_global_info
    from creme.creme_core.utils import (find_first, truncate_str, split_filter,
        create_if_needed, update_model_instance, get_from_GET_or_404, get_from_POST_or_404,
        safe_unicode, int_2_roman, ellipsis, ellipsis_multi, prefixed_truncate) # safe_unicode_error
    from creme.creme_core.utils.dates import (dt_from_str, date_from_str,
        date_from_ISO8601, date_to_ISO8601, date_2_dict,
        dt_from_ISO8601, dt_to_ISO8601, round_hour, to_utc, make_aware_dt)
        # get_dt_to_iso8601_str get_dt_from_iso8601_str get_dt_from_json_str dt_to_json_str get_dt_from_str get_date_from_str
    from creme.creme_core.utils.dependence_sort import dependence_sort, DependenciesLoopError
    from creme.creme_core.utils.log import log_exceptions
    from creme.creme_core.utils.secure_filename import secure_filename
    from creme.creme_core.utils.url import TemplateURLBuilder
except Exception as e:
    print('Error in <{}>: {}'.format(__name__, e))


class MiscTestCase(CremeTestCase):
    def test_find_first(self):
        class Info:
            def __init__(self, data): self.data = data

        i1, i2, i3, i4 = Info(1), Info(2), Info(2), Info(5)
        l = [i1, i2, i3, i4]

        self.assertIs(find_first(l, lambda i: i.data == 1), i1)
        self.assertIs(find_first(l, lambda i: i.data == 2), i2)
        self.assertIs(find_first(l, lambda i: i.data == 5), i4)

        self.assertIsNone(find_first(l, lambda i: i.data == 12, None))
        self.assertRaises(IndexError, find_first, l, lambda i: i.data == 12)

    def test_split_filter(self):
        ok, ko = split_filter((lambda x: x % 2), range(5))
        self.assertEqual([1, 3], ok)
        self.assertEqual([0, 2, 4], ko)

        ok, ko = split_filter((lambda x: 'k' in x), ['Naruto', 'Sasuke', 'Sakura', 'Kakashi'])
        self.assertEqual(['Sasuke', 'Sakura', 'Kakashi'], ok)
        self.assertEqual(['Naruto'], ko)

    def test_truncate_str_01(self):
        s = string.ascii_letters
        self.assertEqual(52, len(s))

        truncated = truncate_str(s, 50)
        self.assertEqual(50,     len(truncated))
        self.assertEqual(s[:-2], truncated)

        expected = s[:-5] + '012'
        self.assertEqual(expected, truncate_str(s, 50, suffix='012'))

        self.assertEqual('',      truncate_str('',        0, suffix='01234'))
        self.assertEqual('01234', truncate_str('abcdef',  5, suffix='01234'))
        self.assertEqual('abc',   truncate_str('abcdef',  3, suffix=''))
        self.assertEqual('',      truncate_str('abcdef', -1, suffix=''))
        self.assertEqual('',      truncate_str('abcdef', -1, suffix='aaaaaa'))
        self.assertEqual('a',     truncate_str('b',       1, suffix='a'))
        self.assertEqual('abcd',  truncate_str('abcdef',  4, suffix='01234'))

    def test_create_if_needed01(self):
        title = 'Mister'
        pk = 1024
        self.assertFalse(FakeCivility.objects.filter(pk=pk).exists())

        civ = create_if_needed(FakeCivility, {'pk': pk}, title=title)
        self.assertIsInstance(civ, FakeCivility)
        self.assertEqual(pk,       civ.pk)
        self.assertEqual(title,    civ.title)

        civ = self.get_object_or_fail(FakeCivility, pk=pk)  # Check has been saved

        self.assertEqual(title, civ.title)

        civ = create_if_needed(FakeCivility, {'pk': pk}, title=title + '2')
        self.assertEqual(title, civ.title)

    # def test_create_if_needed02(self):
    #     user = self.login()
    #     url = '/foo/bar'
    #     label = 'Oh yeah'
    #     order = 3
    #     pmi = create_if_needed(PreferedMenuItem, {'user': user, 'url': url}, label=label, order=order)
    #
    #     self.assertIsInstance(pmi, PreferedMenuItem)
    #     self.assertEqual(user,   pmi.user)
    #     self.assertEqual(url,    pmi.url)
    #     self.assertEqual(label,  pmi.label)
    #     self.assertEqual(order,  pmi.order)
    #
    #     pmi = self.get_object_or_fail(PreferedMenuItem, pk=pmi.pk)  # Check has been saved
    #
    #     self.assertEqual(label,  pmi.label)
    #     self.assertEqual(order,  pmi.order)
    #
    #     pmi = create_if_needed(PreferedMenuItem, {'user': user, 'url': url}, label=label + ' new', order=order + 2)
    #     self.assertEqual(label,  pmi.label)
    #     self.assertEqual(order,  pmi.order)

    def test_update_model_instance01(self):
        self.login()
        first_name = 'punpun'
        last_name = 'punpunyama'
        pupun = FakeContact.objects.create(user=self.user, first_name=first_name, last_name=last_name)

        first_name = first_name.title()

        update_model_instance(pupun, first_name=first_name)
        self.assertEqual(first_name, self.refresh(pupun).first_name)

        with self.assertNumQueries(0):
            update_model_instance(pupun, last_name=last_name)

        self.assertRaises(AttributeError, update_model_instance,
                          pupun, first_name=first_name, unknown_field='??'
                         )

    def test_update_model_instance02(self):
        self.login()

        first_name = 'punpun'
        last_name = 'punpunyama'
        pupun = FakeContact.objects.create(user=self.user, first_name=first_name, last_name=last_name)

        first_name = first_name.title()
        last_name = last_name.title()
        update_model_instance(pupun, first_name=first_name, last_name=last_name)

        pupun = self.refresh(pupun)
        self.assertEqual(first_name, pupun.first_name)
        self.assertEqual(last_name,  pupun.last_name)

        with self.assertNumQueries(0):
            update_model_instance(pupun, first_name=first_name, last_name=last_name)

    def test_get_from_request_or_404(self):
        request = {'name': 'robert', 'age': '36'}

        self.assertRaises(Http404, get_from_GET_or_404, request, 'name_')  # Key error
        self.assertRaises(Http404, get_from_GET_or_404, request, 'name', int)  # Cast error
        self.assertRaises(Http404, get_from_GET_or_404, request, 'name_', int, default='string')  # Cast error

        self.assertEqual('36', get_from_POST_or_404(request, 'age'))
        self.assertEqual(36, get_from_POST_or_404(request, 'age', int))
        self.assertEqual(1,  get_from_POST_or_404(request, 'name_', int, default=1))

    def test_safe_unicode(self):
        # self.assertEqual(u"kjøÔ€ôþâ", safe_unicode(u"kjøÔ€ôþâ"))
        # self.assertEqual(u"aé‡ae15", safe_unicode("a\xe9\x87ae15"))
        # self.assertEqual(u"aé‡ae15", safe_unicode("aé‡ae15"))
        #
        # # Custom encoding list
        # self.assertEqual(u"a\ufffdae15", safe_unicode("a\xe9\x87ae15", ('utf-8',)))
        # self.assertEqual(u"aé‡ae15", safe_unicode("a\xe9\x87ae15", ('cp1252',)))

        # P3K
        self.assertEqual('kjøÔ€ôþâ', safe_unicode('kjøÔ€ôþâ'))
        self.assertEqual('aé‡ae15', safe_unicode(b'a\xe9\x87ae15'))
        self.assertEqual('aé‡ae15', safe_unicode('aé‡ae15'))

        # Custom encoding list
        self.assertEqual(u'a\ufffdae15', safe_unicode(b'a\xe9\x87ae15', ['utf-8']))
        self.assertEqual('aé‡ae15',      safe_unicode(b'a\xe9\x87ae15', ('cp1252',)))

    def test_safe_unicode_object(self):
        # class no_unicode_object:
        #     pass
        #
        # class unicode_object:
        #     def __unicode__(self):
        #         return u"aé‡ae15"
        #
        # class false_unicode_object:
        #     def __init__(self, text):
        #         self.text = text
        #
        #     def __unicode__(self):
        #         return self.text
        #
        # self.assertEqual(u"<class 'creme.creme_core.tests.utils.test_main.no_unicode_object'>",
        #                  safe_unicode(no_unicode_object)
        #                 )
        # self.assertEqual(u"aé‡ae15", safe_unicode(unicode_object()))
        # self.assertEqual(u"aé‡ae15", safe_unicode(false_unicode_object(u"aé‡ae15")))
        # self.assertEqual(u"aé‡ae15", safe_unicode(false_unicode_object("a\xe9\x87ae15")))

        # P3K
        class no_unicode_object:
            pass

        class unicode_object:
            def __str__(self):
                return u'aé‡ae15'

        # class false_unicode_object:
        #     def __init__(self, text):
        #         self.text = text
        #
        #     def __str__(self):
        #         return self.text

        self.assertEqual("<class 'creme.creme_core.tests.utils."
                         "test_main.MiscTestCase.test_safe_unicode_object.<locals>.no_unicode_object'>",
                         safe_unicode(no_unicode_object)
                        )
        self.assertEqual('aé‡ae15', safe_unicode(unicode_object()))
        # self.assertEqual(u"aé‡ae15", safe_unicode(false_unicode_object("a\xe9\x87ae15")))

    # def test_safe_unicode_error1(self):
    #     "Encoding errors"
    #     self.assertEqual(u"kjøÔ€ôþâ", safe_unicode_error(OSError(u"kjøÔ€ôþâ")))
    #     self.assertEqual(u"kjøÔ€ôþâ", safe_unicode_error(Exception(u"kjøÔ€ôþâ")))
    #
    #     self.assertEqual(u"aé‡ae15", safe_unicode_error(OSError("a\xe9\x87ae15")))
    #     self.assertEqual(u"aé‡ae15", safe_unicode_error(Exception("a\xe9\x87ae15")))
    #
    #     self.assertEqual(u"aé‡ae15", safe_unicode_error(OSError("aé‡ae15")))
    #     self.assertEqual(u"aé‡ae15", safe_unicode_error(Exception("aé‡ae15")))
    #
    #     # Custom encoding list
    #     self.assertEqual(u"a\ufffdae15", safe_unicode_error(OSError("a\xe9\x87ae15"), ('utf-8',)))
    #     self.assertEqual(u"a\ufffdae15", safe_unicode_error(Exception("a\xe9\x87ae15"), ('utf-8',)))
    #
    #     self.assertEqual(u"aé‡ae15", safe_unicode_error(OSError("a\xe9\x87ae15"), ('cp1252',)))
    #     self.assertEqual(u"aé‡ae15", safe_unicode_error(Exception("a\xe9\x87ae15"), ('cp1252',)))

    # def test_safe_unicode_error2(self):
    #     "'message' attribute is not a string/unicode (like ExpatError)"
    #     class MyAnnoyingException(Exception):
    #         class MyAnnoyingExceptionMsg:
    #             def __str__(self):
    #                 return u'My message'
    #
    #         def __init__(self):
    #             self.message = self.MyAnnoyingExceptionMsg()
    #
    #         def __str__(self):
    #             return str(self.message)
    #
    #     self.assertEqual(u'My message', safe_unicode_error(MyAnnoyingException()))

    def test_date_2_dict(self):
        d = {'year': 2012, 'month': 6, 'day': 6}
        self.assertEqual(d, date_2_dict(date(**d)))

    def test_int_2_roman(self):
        self.assertEqual(['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X',
                          'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX'
                         ],
                         [int_2_roman(i) for i in range(1, 21)]
                        )
        self.assertEqual('MM',      int_2_roman(2000))
        self.assertEqual('MCMXCIX', int_2_roman(1999))

    def test_ellipsis(self):
        self.assertEqual('123456789', ellipsis('123456789', 9))
        self.assertEqual(u'1234567…', ellipsis('123456789', 8))

    def test_ellipsis_multi(self):
        self.assertEqual(['a', 'b'],
                         ellipsis_multi(['a', 'b'], 10)
                        )
        self.assertEqual(['123456789', 'b'],
                         ellipsis_multi(['123456789', 'b'], 10)
                        )
        self.assertEqual([u'1234567…', 'b'],
                         ellipsis_multi(['123456789', 'b'], 9)
                        )
        self.assertEqual([u'1234…', '12', '12'],
                         ellipsis_multi(['123456', '12', '12'], 9)
                        )
        self.assertEqual([u'12…', '12', u'123…'],  # [u'123…', '12', u'12…'] would be better...
                         ellipsis_multi(['123456', '12', '12345'], 9)
                        )

    def test_prefixed_truncate(self):
        s = 'Supercalifragilis Ticexpialidocious'
        self.assertEqual(s, prefixed_truncate(s, '(My prefix)', 49))
        self.assertEqual('(My prefix)Supercalifragilis Tic', prefixed_truncate(s, '(My prefix)', 32))

        with self.assertRaises(ValueError):
            prefixed_truncate(s, '(My prefix)', 10)  # Prefix is too short for this length

        self.assertEqual('(My unlocated prefix)Supercalif',
                         prefixed_truncate(s, ugettext_lazy('(My unlocated prefix)'), 31)
                        )

    def test_log_exception(self):
        class Logger:
            def __init__(self):
                self.data = []

            def warn(self, s):
                self.data.append(s)

        my_logger = Logger()

        @log_exceptions(printer=my_logger.warn)
        def no_problemo(a, b):
            return a + b

        res = no_problemo(1, b=2)
        self.assertEqual(3, res)
        self.assertFalse(my_logger.data)

        # ----
        @log_exceptions(printer=my_logger.warn)
        def error_paluzza():
            raise ValueError('Mayday')

        with self.assertRaises(ValueError):
            error_paluzza()

        self.assertEqual(1, len(my_logger.data))
        self.assertTrue(my_logger.data[0].startswith('An exception occurred in <error_paluzza>.\n'))

    # TODO: add test for Windows
    def test_secure_filename(self):
        self.assertEqual('My_cool_movie.mov', secure_filename('My cool movie.mov'))
        self.assertEqual('etc_passwd',        secure_filename('../../../etc/passwd'))
        self.assertEqual('i_contain_cool_umlauts.txt',
                         secure_filename(u'i contain cool \xfcml\xe4uts.txt')
                        )
        self.assertEqual('i_contain_weird_characters.txt',
                         secure_filename(u'i contain weird châräctérs.txt')
                        )

        with self.assertNoException():
            size = open_img(join(settings.CREME_ROOT, 'static', 'common', 'images',
                                 secure_filename('500_200.png')
                                )
                           ).size
        self.assertEqual((200, 200), size)


class DependenceSortTestCase(CremeTestCase):  # TODO: SimpleTestCase
    class DepSortable:
        def __init__(self, name, deps=None):
            self.name = name
            self.dependencies = deps or []

        def __repr__(self):
            return self.name

        def key(self):
            return self.name

        def deps(self): 
            return self.dependencies

    def test_dependence_sort01(self):
        self.assertEqual([], dependence_sort([], lambda ds: ds.name, lambda ds: ds.dependencies))

    def test_dependence_sort02(self):
        A = self.DepSortable('A')
        B = self.DepSortable('B')
        self.assertEqual([A, B], 
                         dependence_sort([A, B], lambda ds: ds.name, lambda ds: ds.dependencies)
                        )

    def test_dependence_sort03(self):
        DS = self.DepSortable
        A = DS('A', ['B'])
        B = DS('B')
        self.assertEqual([B, A],
                         dependence_sort([A, B], DS.key, DS.deps)
                        )

    def test_dependence_sort04(self):
        DS = self.DepSortable
        A = DS('A', ['C'])
        B = DS('B')
        C = DS('C', ['B'])
        self.assertEqual([B, C, A], dependence_sort([A, B, C], DS.key, DS.deps))

    def test_dependence_sort05(self):
        DS = self.DepSortable
        A = DS('A', ['C', 'D'])
        B = DS('B')
        C = DS('C', ['B'])
        D = DS('D')
        self.assertIn(dependence_sort([A, B, C, D], DS.key, DS.deps),
                      ([B, D, C, A],
                       [B, C, D, A],
                       [D, B, C, A],
                      )
                     )

    def test_dependence_sort06(self):
        DS = self.DepSortable
        A = DS('A', ['C'])
        B = DS('B')
        C = DS('C', ['A'])

        self.assertRaises(DependenciesLoopError, dependence_sort,
                          [A, B, C], DS.key, DS.deps,
                         )

    def test_dependence_sort07(self):
        DS = self.DepSortable
        A = DS('End', ['Middle'])
        B = DS('Start')
        C = DS('Middle', ['Start'])
        self.assertEqual([B, C, A], dependence_sort([A, B, C], DS.key, DS.deps))


class DatesTestCase(CremeTestCase):
    # def test_get_dt_from_iso8601_str_01(self):
    #     dt = get_dt_from_iso8601_str('20110522T223000Z')
    #     self.assertEqual(datetime(2011, 5, 22, 22, 30, 0), dt)

    # def test_get_dt_to_iso8601_str_01(self):
    #     dt = datetime(2011, 5, 22, 22, 30, 0)
    #     self.assertEqual('20110522T223000Z', get_dt_to_iso8601_str(dt))

    # def test_get_dt_from_json_str(self):
    #     self.assertEqual(self.create_datetime(year=2014, month=3, day=17, hour=15,
    #                                           minute=22, second=3, microsecond=357000,
    #                                           utc=True,
    #                                          ),
    #                      get_dt_from_json_str('2014-03-17T15:22:03.357Z')
    #                     )
    #     self.assertEqual(self.create_datetime(year=2015, month=1, day=16, hour=15,
    #                                           minute=22, second=3, microsecond=123456,
    #                                           utc=True,
    #                                          ),
    #                      get_dt_from_json_str('2015-01-16T15:22:03.123456Z')
    #                     )

    def test_dt_from_ISO8601(self):
        self.assertEqual(self.create_datetime(year=2014, month=3, day=17, hour=15,
                                              minute=22, second=3, microsecond=357000,
                                              utc=True,
                                             ),
                         dt_from_ISO8601('2014-03-17T15:22:03.357Z')
                        )
        self.assertEqual(self.create_datetime(year=2015, month=1, day=16, hour=15,
                                              minute=22, second=3, microsecond=123456,
                                              utc=True,
                                             ),
                         dt_from_ISO8601('2015-01-16T15:22:03.123456Z')
                        )

    # def test_dt_to_json_str(self):
    #     self.assertEqual('2015-01-16T15:22:03.357000Z',
    #                      dt_to_json_str(
    #                          self.create_datetime(year=2015, month=1, day=16, hour=15,
    #                                               minute=22, second=3, microsecond=357000,
    #                                               utc=True,
    #                                              )
    #                         )
    #                     )

    def test_dt_to_ISO8601(self):
        self.assertEqual('2015-01-16T15:22:03.357000Z',
                         dt_to_ISO8601(
                             self.create_datetime(year=2015, month=1, day=16, hour=15,
                                                  minute=22, second=3, microsecond=357000,
                                                  utc=True,
                                                 )
                            )
                        )
        self.assertEqual('2018-02-04T18:41:25.123000Z',
                         dt_to_ISO8601(
                             make_aware(datetime(year=2018, month=2, day=4, hour=19,
                                                 minute=41, second=25, microsecond=123000,
                                                ),
                                        timezone=timezone('Europe/Paris'),  # DST: +1h
                                       )
                            )
                        )
        self.assertEqual('2018-03-05T19:41:25.123000Z',
                         dt_to_ISO8601(datetime(year=2018, month=3, day=5, hour=19,
                                                minute=41, second=25, microsecond=123000,
                                               ),
                                      )
                         )

    # def test_get_dt_from_str(self):
    #     create_dt = self.create_datetime
    #     self.assertEqual(create_dt(year=2013, month=7, day=25, hour=12, minute=28, second=45),
    #                      get_dt_from_str('2013-07-25 12:28:45')
    #                     )
    #     self.assertEqual(create_dt(year=2013, month=7, day=25, hour=8, utc=True),
    #                      get_dt_from_str('2013-07-25 11:00:00+03:00')
    #                     )
    #
    #     DATETIME_INPUT_FORMATS = settings.DATETIME_INPUT_FORMATS
    #
    #     def check(fmt, dt_str, **kwargs):
    #         if fmt in DATETIME_INPUT_FORMATS:
    #             self.assertEqual(create_dt(**kwargs), get_dt_from_str(dt_str))
    #         else:
    #             print('DatesTestCase: skipped datetime format:', fmt)
    #
    #     check('%d-%m-%Y', '25/07/2013', year=2013, month=7, day=25)
    #     check('%Y-%m-%d', '2014-08-26', year=2014, month=8, day=26)
    #
    #     check('%Y-%m-%dT%H:%M:%S.%fZ', '2013-07-25 12:28:45',
    #           year=2013, month=7, day=25, hour=12, minute=28, second=45
    #          )

    def test_dt_from_str(self):
        create_dt = self.create_datetime
        self.assertEqual(create_dt(year=2013, month=7, day=25, hour=12, minute=28, second=45),
                         dt_from_str('2013-07-25 12:28:45')
                        )
        self.assertEqual(create_dt(year=2013, month=7, day=25, hour=8, utc=True),
                         dt_from_str('2013-07-25 11:00:00+03:00')
                        )

        DATETIME_INPUT_FORMATS = settings.DATETIME_INPUT_FORMATS

        def check(fmt, dt_str, **kwargs):
            if fmt in DATETIME_INPUT_FORMATS:
                self.assertEqual(create_dt(**kwargs), dt_from_str(dt_str))
            else:
                print('DatesTestCase: skipped datetime format:', fmt)

        check('%d-%m-%Y', '25/07/2013', year=2013, month=7, day=25)
        check('%Y-%m-%d', '2014-08-26', year=2014, month=8, day=26)

        check('%Y-%m-%dT%H:%M:%S.%fZ', '2013-07-25 12:28:45',
              year=2013, month=7, day=25, hour=12, minute=28, second=45
             )

    # def test_get_date_from_str(self):
    #     DATE_INPUT_FORMATS = settings.DATE_INPUT_FORMATS
    # 
    #     def check(fmt, date_str, **kwargs):
    #         if fmt in DATE_INPUT_FORMATS:
    #             self.assertEqual(date(**kwargs), get_date_from_str(date_str))
    #         else:
    #             print('DatesTestCase: skipped date format:', fmt)
    #
    #     check('%d-%m-%Y', '25/07/2013', year=2013, month=7, day=25)
    #     check('%Y-%m-%d', '2014-08-26', year=2014, month=8, day=26)

    def test_date_from_str(self):
        DATE_INPUT_FORMATS = settings.DATE_INPUT_FORMATS

        def check(fmt, date_str, **kwargs):
            if fmt in DATE_INPUT_FORMATS:
                self.assertEqual(date(**kwargs), date_from_str(date_str))
            else:
                print('DatesTestCase: skipped date format:', fmt)

        check('%d-%m-%Y', '25/07/2013', year=2013, month=7, day=25)
        check('%Y-%m-%d', '2014-08-26', year=2014, month=8, day=26)

    def test_round_datetime(self):
        create_dt = self.create_datetime
        self.assertEqual(create_dt(year=2013, month=7, day=25, hour=12, minute=0, second=0, microsecond=0),
                         round_hour(create_dt(year=2013, month=7, day=25, hour=12, minute=28, second=45, microsecond=516))
                        )

    def test_to_utc(self):
        tz = timezone('Europe/Paris')  # +01:00
        dt = tz.localize(datetime(year=2016, month=11, day=23, hour=18, minute=28), is_dst=True)
        self.assertEqual(datetime(year=2016, month=11, day=23, hour=17, minute=28), to_utc(dt))

    def test_date_from_ISO8601(self):
        self.assertEqual(date(year=2016, month=11, day=23),
                         date_from_ISO8601('2016-11-23')
                        )

    def test_date_to_ISO8601(self):
        self.assertEqual('2016-11-23',
                         date_to_ISO8601(date(year=2016, month=11, day=23))
                        )

    @override_tz('Europe/London')
    def test_make_aware_dt01(self):
        dt = datetime(year=2016, month=12, day=13, hour=14, minute=35)
        self.assertTrue(is_naive(dt))

        dt2 = make_aware_dt(dt)
        self.assertTrue(is_aware(dt2))
        self.assertEqual(2016, dt2.year)
        self.assertEqual(12,   dt2.month)
        self.assertEqual(13,   dt2.day)
        self.assertEqual(14,   dt2.hour)
        self.assertEqual(35,   dt2.minute)
        self.assertEqual(timedelta(hours=0), dt2.tzinfo.utcoffset(dt2))

    @override_tz('Europe/Paris')
    def test_make_aware_dt02(self):
        dt = make_aware_dt(datetime(year=2016, month=12, day=13, hour=14, minute=35))
        self.assertTrue(is_aware(dt))
        self.assertEqual(2016, dt.year)
        self.assertEqual(12,   dt.month)
        self.assertEqual(13,   dt.day)
        self.assertEqual(14,   dt.hour)
        self.assertEqual(35,   dt.minute)
        self.assertEqual(timedelta(hours=1), dt.tzinfo.utcoffset(dt))

    @override_tz('Europe/Paris')  # This Time zone uses daylight saving time (DST)
    def test_make_aware_dt03(self):
        with self.assertNoException():
            # NB: date of change for the UTC offset
            dt = make_aware_dt(datetime(year=2016, month=10, day=30, hour=2, minute=30))

        self.assertTrue(is_aware(dt))
        self.assertEqual(2016, dt.year)
        self.assertEqual(10,   dt.month)
        self.assertEqual(30,   dt.day)
        self.assertEqual(2,    dt.hour)
        self.assertEqual(30,   dt.minute)
        self.assertEqual(timedelta(hours=1), dt.tzinfo.utcoffset(dt))


class UnicodeCollationTestCase(CremeTestCase):
    def test_uca01(self):
        from creme.creme_core.utils.unicode_collation import collator

        sort = partial(sorted, key=collator.sort_key)
        words = ['Caff', 'Cafe', 'Cafard', u'Café']
        self.assertEqual(['Cafard', 'Cafe', 'Caff', u'Café'], sorted(words))  # Standard sort
        self.assertEqual(['Cafard', 'Cafe', u'Café', 'Caff'], sort(words))

        self.assertEqual(['La', u'Là', u'Lä', 'Las', 'Le'],
                         sort(['La', u'Là', 'Le', u'Lä', 'Las'])
                        )
        self.assertEqual(['gloves', u'ĝloves', 'hats', 'shoes'],
                         sort(['hats', 'gloves', 'shoes', u'ĝloves']),
                        )

    # NB: keep this comment (until we use the real 'pyuca' lib)
    # def test_uca02(self):
    #     "Original lib"
    #     from os.path import join
    #     from pyuca import Collator
    #
    #     path = join(settings.CREME_ROOT, 'creme_core', 'utils', 'allkeys.txt')
    #     collator = Collator(path)
    #     sort = partial(sorted, key=collator.sort_key)
    #     words = ['Caff', 'Cafe', 'Cafard', u'Café']
    #     self.assertEqual(['Cafard', 'Cafe', 'Caff', u'Café'], sorted(words)) # standard sort
    #     self.assertEqual(['Cafard', 'Cafe', u'Café', 'Caff'], sort(words))
    #
    #     self.assertEqual(['La', u'Là', u'Lä', 'Las', 'Le'],
    #                      sort(['La', u'Là', 'Le', u'Lä', 'Las'])
    #                     )
    #     self.assertEqual(['gloves', u'ĝloves', 'hats', 'shoes'],
    #                      sort(['hats', 'gloves', 'shoes', u'ĝloves']),
    #                     )
    #
    #     #test memory comsumption
    #     #from time import sleep
    #     #sleep(10)


class CurrencyFormatTestCase(CremeTestCase):
    def test_currency(self):
        from decimal import Decimal

        from creme.creme_core.constants import DISPLAY_CURRENCY_LOCAL_SYMBOL
        from creme.creme_core.models import Currency, SettingValue
        from creme.creme_core.utils.currency_format import currency

        sv = self.get_object_or_fail(SettingValue, key_id=DISPLAY_CURRENCY_LOCAL_SYMBOL)
        self.assertTrue(sv.value)

        result1 = currency(3)
        self.assertIsInstance(result1, str)
        self.assertIn('3', result1)

        result2 = currency(3, currency_or_id=None)
        self.assertEqual(result1, result2)

        result3 = currency(Decimal('3.52'))
        self.assertIn('3',  result3)
        self.assertIn('52', result3)

        my_currency = Currency.objects.all()[0]
        result4 = currency(5, currency_or_id=my_currency)
        self.assertIn('5', result4)
        self.assertIn(my_currency.local_symbol, result4)
        self.assertNotIn(my_currency.international_symbol, result4)

        sv.value = False
        sv.save()
        clear_global_info()
        result5 = currency(5, currency_or_id=my_currency)
        self.assertIn('5', result5)
        self.assertIn(my_currency.international_symbol, result5)
        self.assertNotIn(my_currency.local_symbol, result5)

        result6 = currency(5, currency_or_id=my_currency.id)
        self.assertEqual(result5, result6)

        result7 = currency(-5, currency_or_id=my_currency)
        self.assertNotEqual(result6, result7)


class TemplateURLBuilderTestCase(CremeTestCase):
    def test_place_holder01(self):
        "Word"
        ph = TemplateURLBuilder.Word('$name', 'name')
        self.assertEqual('__placeholder0__', ph.tmp_name(0, 0))
        self.assertEqual('__placeholder1__', ph.tmp_name(1, 0))
        self.assertEqual('__PLACEHOLDER0__', ph.tmp_name(0, 1))

    def test_place_holder02(self):
        "Int"
        ph = TemplateURLBuilder.Int('$ct_id', 'ctype_id')
        self.assertEqual('1234567890', ph.tmp_name(0, 0))
        self.assertEqual('1234567891', ph.tmp_name(1, 0))
        self.assertEqual('9876543210', ph.tmp_name(0, 1))

    def test_one_place_holder01(self):
        "Word place holder"
        vname = 'creme_core__batch_process_ops'
        placeholder = 'XXXXXX'
        final_value = '${name}'  # This string does not match with (?P<field>[\w]+)

        tub = TemplateURLBuilder(field=(TemplateURLBuilder.Word, final_value))

        self.assertEqual(reverse(vname, args=(65, placeholder)).replace(placeholder, final_value),
                         tub.resolve(vname, kwargs={'ct_id': 65})
                        )

    def test_one_place_holder02(self):
        "Int place holder"
        vname = 'creme_core__batch_process_ops'
        placeholder = '123456'
        final_value = '${ct}'  # This string does not match with (?P<ct_id>\d+)

        tub = TemplateURLBuilder(ct_id=(TemplateURLBuilder.Int, final_value))

        self.assertEqual(reverse(vname, args=(placeholder, 'name')).replace(placeholder, final_value),
                         tub.resolve(vname, kwargs={'field': 'name'})
                        )

    def test_two_place_holders01(self):
        "1 word & 1 int place holders"
        vname = 'creme_core__batch_process_ops'
        placeholder1 = '123456'; final_value1 = '${ct}'
        placeholder2 = 'XXXXXX'; final_value2 = '${name}'

        tub = TemplateURLBuilder(ct_id=(TemplateURLBuilder.Int,  final_value1),
                                 field=(TemplateURLBuilder.Word, final_value2),
                                )

        self.assertEqual(reverse(vname, args=(placeholder1, placeholder2)).replace(placeholder1, final_value1)
                                                                          .replace(placeholder2, final_value2),
                         tub.resolve(vname)
                        )

    def test_two_place_holders02(self):
        # "2 int place holders"
        "2 int & 1 word place holders"
        # vname = 'creme_core__merge_entities'
        vname = 'creme_core__inner_edition'

        placeholder1 = '123456'; final_value1 = '${id1}'
        placeholder2 = '789456'; final_value2 = '${id2}'
        placeholder3 = 'fobbar'; final_value3 = '${fname}'

        # tub = TemplateURLBuilder(entity1_id=(TemplateURLBuilder.Int, final_value1),
        #                          entity2_id=(TemplateURLBuilder.Int, final_value2),
        #                         )
        tub = TemplateURLBuilder(ct_id=(TemplateURLBuilder.Int, final_value1),
                                 id=(TemplateURLBuilder.Int, final_value2),
                                 field_name=(TemplateURLBuilder.Word, final_value3),
                                )

        # self.assertEqual(reverse(vname, args=(placeholder1, placeholder2)).replace(placeholder1, final_value1)
        #                                                                   .replace(placeholder2, final_value2),
        #                  tub.resolve(vname)
        #                 )
        self.assertEqual(reverse(vname, args=(placeholder1, placeholder2, placeholder3))
                                .replace(placeholder1, final_value1)
                                .replace(placeholder2, final_value2)
                                .replace(placeholder3, final_value3),
                         tub.resolve(vname)
                        )
