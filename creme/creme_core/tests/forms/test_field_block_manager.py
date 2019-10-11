# -*- coding: utf-8 -*-

try:
    from django.utils.translation import gettext as _

    from ..base import CremeTestCase
    from ..fake_forms import FakeContactForm
except Exception as e:
    print('Error in <{}>: {}'.format(__name__, e))


class FieldBlockManagerTestCase(CremeTestCase):
    def test_iter(self):
        user = self.login()

        block_vname = 'Particulars'

        class TestFakeContactForm(FakeContactForm):
            blocks = FakeContactForm.blocks.new(('particulars', block_vname,
                                                 ['phone', 'mobile', 'email', 'url_site']
                                                )
                                               )

        blocks_group = TestFakeContactForm(user=user).get_blocks()
        blocks = list(blocks_group)

        self.assertEqual(5, len(blocks))

        # ------------------
        block1 = blocks[0]
        self.assertIsInstance(block1, tuple)
        self.assertEqual(2, len(block1))
        self.assertEqual(_('General information'), str(block1[0]))

        fields = block1[1]
        self.assertIsInstance(fields, list)

        with self.assertNoException():
            bfield, required = fields[0]

        self.assertIs(required, True)
        self.assertFalse(bfield.is_hidden)
        self.assertEqual('id_user', bfield.auto_id)

        # ------------------
        self.assertEqual(_('Description'),   str(blocks[1][0]))
        self.assertEqual(_('Properties'),    str(blocks[2][0]))
        self.assertEqual(_('Relationships'), str(blocks[3][0]))

        # ------------------
        block5 = blocks[4]
        self.assertEqual(block_vname, block5[0])

        fields = block5[1]
        self.assertEqual(4, len(fields))
        self.assertEqual('id_phone', fields[0][0].auto_id)

    def test_getitem(self):
        user = self.login()

        block_id = 'particulars'
        block_vname = 'Particulars'

        class TestFakeContactForm(FakeContactForm):
            blocks = FakeContactForm.blocks.new(
                (block_id, block_vname, ['phone', 'mobile', 'email', 'url_site']),
            )

        blocks_group = TestFakeContactForm(user=user).get_blocks()

        with self.assertNoException():
            general_block = blocks_group['general']

        self.assertEqual(_('General information'), str(general_block[0]))

        with self.assertNoException():
            p_block = blocks_group[block_id]

        self.assertEqual(block_vname, p_block[0])

        fields = p_block[1]
        self.assertEqual(4, len(fields))
        self.assertEqual('id_mobile', fields[1][0].auto_id)

    def test_invalid_field(self):
        user = self.login()

        block_id = 'particulars'
        block_vname = 'Particulars'

        class TestFakeContactForm(FakeContactForm):
            class Meta(FakeContactForm.Meta):
                exclude = ('mobile', )  # <===

            blocks = FakeContactForm.blocks.new((block_id, block_vname,
                                                 # 'mobile' is excluded
                                                 ['phone', 'mobile', 'email', 'url_site']
                                                )
                                               )

        form = TestFakeContactForm(user=user)

        with self.assertNoException():
            block = form.get_blocks()[block_id]

        self.assertEqual(block_vname, block[0])

        fields = block[1]
        self.assertEqual(3, len(fields))
        self.assertEqual('id_email', fields[1][0].auto_id)
