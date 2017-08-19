# -*- coding: utf-8 -*-

try:
    from django.conf import settings
    from django.template import Template, Context

    from ..base import CremeTestCase
    from ..fake_models import FakeOrganisation, FakeSector
except Exception as e:
    print('Error in <%s>: %s' % (__name__, e))


class CremeWidgetsTagsTestCase(CremeTestCase):
    def test_widget_hyperlink01(self):
        "No get_absolute_url()"
        s = FakeSector(title='<i>Yello</i>')

        with self.assertNoException():
            tpl = Template(r'{% load creme_widgets %}{% widget_hyperlink object %}')
            render = tpl.render(Context({'object': s}))

        self.assertEqual(render, u'&lt;i&gt;Yello&lt;/i&gt;')

    def test_widget_hyperlink02(self):
        "get_absolute_url()"
        s = FakeSector(title='Yello<br>')
        s.get_absolute_url = lambda: '/creme_core/sectors'

        with self.assertNoException():
            tpl = Template(r'{% load creme_widgets %}{% widget_hyperlink object %}')
            render = tpl.render(Context({'object': s}))

        self.assertEqual(render, u'<a href="/creme_core/sectors">Yello&lt;br&gt;</a>')

    def test_widget_entity_hyperlink01(self):
        "Escaping"
        user = self.login()

        name = 'NERV'
        orga = FakeOrganisation.objects.create(user=user, name=name + '<br/>')  # escaping OK ??

        with self.assertNoException():
            tpl = Template(r'{% load creme_widgets %}{% widget_entity_hyperlink my_entity user %}')
            render = tpl.render(Context({'user': user, 'my_entity': orga}))

        self.assertEqual(render,
                         u'<a href="/tests/organisation/%s">%s</a>' % (
                                orga.id, name + '&lt;br/&gt;'
                            )
                        )

    def test_widget_entity_hyperlink02(self):
        "Credentials"
        user = self.login(is_superuser=False)

        orga = FakeOrganisation.objects.create(user=self.other_user, name='NERV')
        self.assertFalse(user.has_perm_to_view(orga))

        with self.assertNoException():
            tpl = Template(r'{% load creme_widgets %}{% widget_entity_hyperlink orga user %}')
            render = tpl.render(Context({'user': user, 'orga': orga}))

        self.assertEqual(render, settings.HIDDEN_VALUE)

    def test_widget_entity_hyperlink03(self):
        "Is deleted"
        user = self.login()
        orga = FakeOrganisation.objects.create(user=user, name='Seele', is_deleted=True)

        with self.assertNoException():
            tpl = Template(r'{% load creme_widgets %}{% widget_entity_hyperlink my_entity user %}')
            render = tpl.render(Context({'user': user, 'my_entity': orga}))

        self.assertEqual(render, 
                         u'<a href="/tests/organisation/%s" class="is_deleted">%s</a>' % (
                                orga.id, unicode(orga)
                            )
                        )

    # TODO: complete
