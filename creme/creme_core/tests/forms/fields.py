# -*- coding: utf-8 -*-

try:
    from django.core.exceptions import ValidationError

    from creme_core.forms.fields import DateRangeField, ColorField, DurationField
    from creme_core.tests.forms.base import FieldTestCase
except Exception as e:
    print 'Error:', e


__all__ = ('DateRangeFieldTestCase', 'ColorFieldTestCase', 'DurationFieldTestCase')


class DateRangeFieldTestCase(FieldTestCase):
    def test_clean_empty_customized(self):
        clean = DateRangeField().clean
        self.assertFieldValidationError(DateRangeField, 'customized_empty', clean, [u"", u"", u""])
        self.assertFieldValidationError(DateRangeField, 'customized_empty', clean, None)

    def test_start_before_end(self):
        self.assertFieldValidationError(DateRangeField, 'customized_invalid',
                                        DateRangeField().clean, [u"", u"2011-05-16", u"2011-05-15"]
                                       )


class ColorFieldTestCase(FieldTestCase):
    def test_empty01(self):
        clean = ColorField().clean
        self.assertFieldValidationError(ColorField, 'required', clean, None)
        self.assertFieldValidationError(ColorField, 'required', clean, '')
        self.assertFieldValidationError(ColorField, 'required', clean, [])

    def test_length01(self):
        clean = ColorField().clean
        self.assertFieldRaises(ValidationError, clean, '1')
        self.assertFieldRaises(ValidationError, clean, '12')
        self.assertFieldRaises(ValidationError, clean, '123')
        self.assertFieldRaises(ValidationError, clean, '1234')
        self.assertFieldRaises(ValidationError, clean, '12345')

    def test_invalid_value01(self):
        clean = ColorField().clean
        self.assertFieldValidationError(ColorField, 'invalid', clean, 'GGGGGG')
        self.assertFieldValidationError(ColorField, 'invalid', clean, '------')

    def test_ok01(self):
        clean = ColorField().clean
        self.assertEqual('AAAAAA', clean('AAAAAA'))
        self.assertEqual('AAAAAA', clean('aaaaaa'))
        self.assertEqual('123456', clean('123456'))
        self.assertEqual('123ABC', clean('123ABC'))
        self.assertEqual('123ABC', clean('123abc'))


class DurationFieldTestCase(FieldTestCase):
    def test_empty01(self):
        clean = DurationField().clean
        self.assertFieldValidationError(DurationField, 'required', clean, None)
        self.assertFieldValidationError(DurationField, 'required', clean, '')
        self.assertFieldValidationError(DurationField, 'required', clean, [])

    def test_invalid01(self):
        self.assertFieldValidationError(DurationField, 'invalid', DurationField().clean, [u'a', u'b', u'c'])

    def test_positive01(self):
        self.assertFieldValidationError(DurationField, 'min_value', DurationField().clean,
                                        [u'-1', u'-1', u'-1'], message_args={'limit_value': 0}
                                       )

    def test_ok01(self):
        clean = DurationField().clean
        self.assertEqual('10:2:0', clean([u'10', u'2', u'0']))
        self.assertEqual('10:2:0', clean([10, 2, 0]))
