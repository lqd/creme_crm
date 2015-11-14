# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2015  Hybird
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

from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext_lazy as _, ugettext

from creme.creme_core.auth import build_creation_perm as cperm
from creme.creme_core.auth.decorators import login_required, permission_required
from creme.creme_core.utils import get_from_POST_or_404
from creme.creme_core.views.generic import (add_entity, add_to_entity,
        edit_entity, view_entity, list_view)

from .. import get_emailtemplate_model
#from ..models import EmailTemplate
from ..forms.template import EmailTemplateForm, EmailTemplateAddAttachment


EmailTemplate = get_emailtemplate_model()


@login_required
# @permission_required(('emails', 'emails.add_emailtemplate'))
@permission_required(('emails', cperm(EmailTemplate)))
def add(request):
    return add_entity(request, EmailTemplateForm,
                      extra_template_dict={'submit_label': _('Save the template')},
                     )

@login_required
@permission_required('emails')
def edit(request, template_id):
    return edit_entity(request, template_id, EmailTemplate, EmailTemplateForm)

@login_required
@permission_required('emails')
def detailview(request, template_id):
    return view_entity(request, template_id, EmailTemplate, '/emails/template',
                       'emails/view_template.html',
                      )

@login_required
@permission_required('emails')
def listview(request):
    return list_view(request, EmailTemplate,
                     # extra_dict={'add_url': '/emails/template/add'}
                     extra_dict={'add_url': reverse('emails__create_template')},
                    )

@login_required
@permission_required('emails')
def add_attachment(request, template_id):
    return add_to_entity(request, template_id, EmailTemplateAddAttachment,
                         ugettext(u'New attachments for «%s»'),
                         entity_class=EmailTemplate,
                         submit_label=_('Save the attachments'),
                        )

@login_required
@permission_required('emails')
def delete_attachment(request, template_id):
    attachment_id = get_from_POST_or_404(request.POST, 'id')
    template = get_object_or_404(EmailTemplate, pk=template_id)

    request.user.has_perm_to_change_or_die(template)

    template.attachments.remove(attachment_id)

    if request.is_ajax():
        return HttpResponse("", content_type="text/javascript")

    return redirect(template)
