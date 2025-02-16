################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2022  Hybird
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
################################################################################

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from creme.creme_core.models import CremeEntity


class AbstractMessagingList(CremeEntity):
    name = models.CharField(_('Name'), max_length=80)
    contacts = models.ManyToManyField(
        settings.PERSONS_CONTACT_MODEL,
        verbose_name=_('Contacts recipients'), editable=False,
    )

    creation_label = _('Create a messaging list')
    save_label     = _('Save the messaging list')

    class Meta:
        abstract = True
        app_label = 'sms'
        verbose_name = _('SMS messaging list')
        verbose_name_plural = _('SMS messaging lists')
        ordering = ('name',)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('sms__view_mlist', args=(self.id,))

    @staticmethod
    def get_create_absolute_url():
        return reverse('sms__create_mlist')

    def get_edit_absolute_url(self):
        return reverse('sms__edit_mlist', args=(self.id,))

    @staticmethod
    def get_lv_absolute_url():
        return reverse('sms__list_mlists')

    def _post_save_clone(self, source):
        for recipient in source.recipient_set.all():
            recipient.clone(self)


class MessagingList(AbstractMessagingList):
    class Meta(AbstractMessagingList.Meta):
        swappable = 'SMS_MLIST_MODEL'
