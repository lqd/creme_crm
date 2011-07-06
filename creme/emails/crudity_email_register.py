# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2010  Hybird
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

import os
from itertools import chain

from django.utils.translation import ugettext as _

from creme_core.models import Relation
from creme_core.views.file_handling import handle_uploaded_file

from django.conf import settings

from crudity.models import History
from crudity import CREATE
from crudity.backends.email import CreateFromEmailBackend

from documents.models import Document, Folder, FolderCategory
from documents.constants import REL_OBJ_RELATED_2_DOC, DOCUMENTS_FROM_EMAILS

from emails.models.mail import EntityEmail, MAIL_STATUS_SYNCHRONIZED_WAITING
from emails.blocks import WaitingSynchronizationMailsBlock, SpamSynchronizationMailsBlock


create_email_settings = settings.EMAILS_ENTITYEMAIL_FROM_EMAIL.get(CREATE)

CREATE_ENTITYEMAIL_LIMIT_FROMS = create_email_settings.get("limit_froms")
CREATE_ENTITYEMAIL_IN_SANDBOX  = create_email_settings.get("in_sandbox", True)
CREATE_ENTITYEMAIL_BODY_MAP    = create_email_settings.get("body_map", {})


class CreateEntityEmailFromEmail(CreateFromEmailBackend):
    """This backend is implemented as the default backend so there are no
    password or subject verification
    """
    password        = None
    limit_froms     = CREATE_ENTITYEMAIL_LIMIT_FROMS
    in_sandbox      = CREATE_ENTITYEMAIL_IN_SANDBOX
    body_map        = CREATE_ENTITYEMAIL_BODY_MAP
    model           = EntityEmail
    subject         = None
    attachment_path = ['upload','emails','attachments']
    blocks          = (WaitingSynchronizationMailsBlock, SpamSynchronizationMailsBlock)

    #def __init__(self):
        #super(CreateEntityEmailFromEmail, self).__init__()

    def create(self, email, current_user):
        if not self.authorize_senders(email.senders):
            return

        if self.is_sandbox_by_user:
            current_user = self.get_owner(sender=email.senders[0])

        current_user_id = current_user.id
        folder_cat, is_cat_created = FolderCategory.objects.get_or_create(pk=DOCUMENTS_FROM_EMAILS)
        folder, is_fold_created = Folder.objects.get_or_create(title=_(u"%(username)s's files received by email") % {'username': current_user.username},
                                                               user=current_user,
                                                               category=folder_cat)

        mail = EntityEmail(status = MAIL_STATUS_SYNCHRONIZED_WAITING,
                           body   = email.body.encode('utf-8'),
                           body_html = email.body_html.encode('utf-8'),
                           sender    = u', '.join(set(email.senders)),
                           recipient = u', '.join(set(chain(email.tos, email.ccs))),
                           subject   = email.subject,
                           user_id   = current_user_id)
        if email.dates:
            mail.reception_date = email.dates[0]
        mail.genid_n_save()

        attachment_path = self.attachment_path
        create_relation = Relation.objects.create

        doc_description = _(u"Received with the mail %s") % (mail, )

        for attachment in email.attachments:
            filename, file = attachment
            path = handle_uploaded_file(file, path=attachment_path, name=filename)
            doc = Document.objects.create(
                    title = u"%s (mail %s)" % (path.rpartition(os.sep)[2], mail.id),
                    description =  doc_description,
                    filedata = path,
                    user_id = current_user_id,
                    folder = folder
            )

            #Relation.create(doc, REL_OBJ_RELATED_2_DOC, mail)
            create_relation(subject_entity=doc, type_id=REL_OBJ_RELATED_2_DOC,
                            object_entity=mail, user_id=current_user_id
                           )

        history = History.objects.create(
            entity = mail,
            type = self.type,
            description = _(u"Creation of %(entity)s") % {'entity': mail},
            user = current_user
        )


crud_register = {
    CREATE: [
        ("*", CreateEntityEmailFromEmail()),
    ],
}
