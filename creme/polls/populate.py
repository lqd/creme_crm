# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2012-2015  Hybird
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

import logging

from django.apps import apps
#from django.conf import settings
from django.utils.translation import ugettext as _

from creme.creme_core.core.entity_cell import EntityCellRegularField
from creme.creme_core.models import HeaderFilter, BlockDetailviewLocation, SearchConfigItem
from creme.creme_core.utils import create_if_needed
from creme.creme_core.blocks import properties_block, relations_block, customfields_block, history_block
from creme.creme_core.management.commands.creme_populate import BasePopulator

from creme.persons import get_contact_model, get_organisation_model
#from creme.persons.models import Contact, Organisation

from . import get_pollform_model, get_pollreply_model, get_pollcampaign_model
from .blocks import *
#from .models import PollType, PollForm, PollReply, PollCampaign
from .models import PollType

logger = logging.getLogger(__name__)


class Populator(BasePopulator):
    dependencies = ['creme_core', 'persons']

    def populate(self, *args, **kwargs):
        PollCampaign = get_pollcampaign_model()
        PollForm     = get_pollform_model()
        PollReply    = get_pollreply_model()
    
        Contact = get_contact_model()
        Organisation = get_organisation_model()

        create_hf = HeaderFilter.create
        create_hf(pk='polls-hf_pollform', name=_(u'Form view'), model=PollForm,
                  cells_desc=[(EntityCellRegularField, {'name': 'name'}),
                             ],
                 )
        create_hf(pk='polls-hf_pollreply', name=_(u'Reply view'), model=PollReply,
                  cells_desc=[(EntityCellRegularField, {'name': 'name'}),
                              (EntityCellRegularField, {'name': 'pform'}),
                              (EntityCellRegularField, {'name': 'person'}),
                             ],
                 )
        create_hf(pk='polls-hf_pollcampaign', name=_(u'Campaign view'), model=PollCampaign,
                  cells_desc=[(EntityCellRegularField, {'name': 'name'}),
                              (EntityCellRegularField, {'name': 'due_date'}),
                              (EntityCellRegularField, {'name': 'segment'}),
                             ],
                 )


        create_searchconf = SearchConfigItem.create_if_needed
        create_searchconf(PollForm,     ['name'])
        create_searchconf(PollReply,    ['name'])
        create_searchconf(PollCampaign, ['name'])


        if not PollType.objects.exists(): # NB: no straightforward way to test that this populate script has not been already runned
            create_if_needed(PollType, {'pk': 1}, name=_(u'Survey'))
            create_if_needed(PollType, {'pk': 2}, name=_(u'Monitoring'))
            create_if_needed(PollType, {'pk': 3}, name=_(u'Assessment'))


        if not BlockDetailviewLocation.config_exists(PollForm): # NB: no straightforward way to test that this populate script has not been already runned
            create_bdl = BlockDetailviewLocation.create
            create_bdl(block_id=pform_lines_block.id_,    order=5,   zone=BlockDetailviewLocation.TOP,   model=PollForm)
            BlockDetailviewLocation.create_4_model_block(order=5,    zone=BlockDetailviewLocation.LEFT,  model=PollForm)
            create_bdl(block_id=customfields_block.id_,   order=40,  zone=BlockDetailviewLocation.LEFT,  model=PollForm)
            create_bdl(block_id=properties_block.id_,     order=450, zone=BlockDetailviewLocation.LEFT,  model=PollForm)
            create_bdl(block_id=relations_block.id_,      order=500, zone=BlockDetailviewLocation.LEFT,  model=PollForm)
            create_bdl(block_id=preplies_block.id_,       order=5,   zone=BlockDetailviewLocation.RIGHT, model=PollForm)
            create_bdl(block_id=history_block.id_,        order=20,  zone=BlockDetailviewLocation.RIGHT, model=PollForm)

            #TODO: factorise
            create_bdl(block_id=preply_lines_block.id_,     order=5,   zone=BlockDetailviewLocation.TOP,   model=PollReply)
            BlockDetailviewLocation.create_4_model_block(order=5,      zone=BlockDetailviewLocation.LEFT,  model=PollReply)
            create_bdl(block_id=customfields_block.id_  ,   order=40,  zone=BlockDetailviewLocation.LEFT,  model=PollReply)
            create_bdl(block_id=properties_block.id_,       order=450, zone=BlockDetailviewLocation.LEFT,  model=PollReply)
            create_bdl(block_id=relations_block.id_,        order=500, zone=BlockDetailviewLocation.LEFT,  model=PollReply)
            create_bdl(block_id=history_block.id_,          order=20,  zone=BlockDetailviewLocation.RIGHT, model=PollReply)

            BlockDetailviewLocation.create_4_model_block(order=5,       zone=BlockDetailviewLocation.LEFT,  model=PollCampaign)
            create_bdl(block_id=customfields_block.id_,      order=40,  zone=BlockDetailviewLocation.LEFT,  model=PollCampaign)
            create_bdl(block_id=properties_block.id_,        order=450, zone=BlockDetailviewLocation.LEFT,  model=PollCampaign)
            create_bdl(block_id=relations_block.id_,         order=500, zone=BlockDetailviewLocation.LEFT,  model=PollCampaign)
            create_bdl(block_id=pcampaign_replies_block.id_, order=5,   zone=BlockDetailviewLocation.RIGHT, model=PollCampaign)
            create_bdl(block_id=history_block.id_,           order=20,  zone=BlockDetailviewLocation.RIGHT, model=PollCampaign)

            create_bdl(block_id=related_preplies_block.id_, order=500, zone=BlockDetailviewLocation.RIGHT,  model=Contact)
            create_bdl(block_id=related_preplies_block.id_, order=500, zone=BlockDetailviewLocation.RIGHT,  model=Organisation)


            if apps.is_installed('creme.assistants'):
                logger.info('Assistants app is installed => we use the assistants blocks on detail view')

                from creme.assistants.blocks import alerts_block, memos_block, todos_block, messages_block

                for model in (PollForm, PollReply, PollCampaign):
                    create_bdl(block_id=todos_block.id_,    order=100, zone=BlockDetailviewLocation.RIGHT, model=model)
                    create_bdl(block_id=memos_block.id_,    order=200, zone=BlockDetailviewLocation.RIGHT, model=model)
                    create_bdl(block_id=alerts_block.id_,   order=300, zone=BlockDetailviewLocation.RIGHT, model=model)
                    create_bdl(block_id=messages_block.id_, order=400, zone=BlockDetailviewLocation.RIGHT, model=model)
