################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2021  Hybird
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

from django.db.transaction import atomic
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from creme.creme_core.models import CremePropertyType
from creme.creme_core.views import generic

from ..forms import creme_property_type as ptype_forms
from . import base


class Portal(generic.BricksView):
    template_name = 'creme_config/portals/property-type.html'


class PropertyTypeCreation(base.ConfigModelCreation):
    model = CremePropertyType
    form_class = ptype_forms.CremePropertyTypeAddForm
    title = _('New custom type of property')


class PropertyTypeEdition(base.ConfigModelEdition):
    # model = CremePropertyType
    queryset = CremePropertyType.objects.filter(is_custom=True, enabled=True)
    form_class = ptype_forms.CremePropertyTypeEditForm
    pk_url_kwarg = 'ptype_id'
    title = pgettext_lazy('creme_config-property', 'Edit the type «{object}»')


# TODO: factorise with Job ?
class PropertyTypeEnabling(generic.CheckedView):
    permissions = base._PERM
    pk_url_kwarg = 'ptype_id'
    enabled_arg = 'enabled'
    enabled_default = True

    @atomic
    def post(self, *args, **kwargs):
        ptype = get_object_or_404(
            CremePropertyType.objects.select_for_update(),
            id=kwargs[self.pk_url_kwarg],
        )

        ptype.enabled = kwargs.get(self.enabled_arg, self.enabled_default)
        ptype.save()

        return HttpResponse()
