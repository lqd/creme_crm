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

from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType

from creme_core.models import Relation
from creme_core.gui.block import QuerysetBlock

from persons.models import Contact

from products.models import Product, Service

from billing.models import Quote, Invoice, SalesOrder

from constants import *
from models import Opportunity


__all__ = ['linked_contacts_block', 'linked_products_block', 'linked_services_block',
           'responsibles_block', 'quotes_block', 'sales_orders_block', 'invoices_block',
           'target_organisation_block']

_contact_ct_id = None

class LinkedContactsBlock(QuerysetBlock):
    id_           = QuerysetBlock.generate_id('opportunities', 'linked_contacts')
    dependencies  = (Relation,) #Contact
    relation_type_deps = (REL_OBJ_LINKED_CONTACT, )
    verbose_name  = _(u'Linked Contacts')
    template_name = 'opportunities/templatetags/block_contacts.html'

    def detailview_display(self, context):
        global _contact_ct_id

        opp = context['object']

        if not _contact_ct_id:
            _contact_ct_id = ContentType.objects.get_for_model(Contact).id

        return self._render(self.get_block_template_context(context, opp.get_contacts(),
                                                            update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, opp.pk),
                                                            predicate_id=REL_OBJ_LINKED_CONTACT,
                                                            ct_id=_contact_ct_id))


class LinkedProductsBlock(QuerysetBlock):
    id_           = QuerysetBlock.generate_id('opportunities', 'linked_products')
    dependencies  = (Relation,)
    relation_type_deps = (REL_OBJ_LINKED_PRODUCT, )
    verbose_name  = _(u'Linked Products')
    template_name = 'opportunities/templatetags/block_products.html'

    def __init__(self, *args, **kwargs):
        super(LinkedProductsBlock, self).__init__(*args, **kwargs)

        self._product_ct_id = None

    def detailview_display(self, context):
        opp = context['object']

        if not self._product_ct_id:
            self._product_ct_id = ContentType.objects.get_for_model(Product).id

        return self._render(self.get_block_template_context(context, opp.get_products(),
                                                            update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, opp.pk),
                                                            predicate_id=REL_OBJ_LINKED_PRODUCT,
                                                            ct_id=self._product_ct_id))


class LinkedServicesBlock(QuerysetBlock):
    id_           = QuerysetBlock.generate_id('opportunities', 'linked_services')
    dependencies  = (Relation,)
    relation_type_deps = (REL_OBJ_LINKED_SERVICE, )
    verbose_name  = _(u'Linked Services')
    template_name = 'opportunities/templatetags/block_services.html'

    def __init__(self, *args, **kwargs):
        super(LinkedServicesBlock, self).__init__(*args, **kwargs)

        self._service_ct_id = None

    def detailview_display(self, context):
        opp = context['object']

        if not self._service_ct_id:
            self._service_ct_id = ContentType.objects.get_for_model(Service).id

        return self._render(self.get_block_template_context(context, opp.get_services(),
                                                            update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, opp.pk),
                                                            predicate_id=REL_OBJ_LINKED_SERVICE,
                                                            ct_id=self._service_ct_id))


class ResponsiblesBlock(QuerysetBlock):
    id_           = QuerysetBlock.generate_id('opportunities', 'responsibles')
    dependencies  = (Relation,)
    relation_type_deps = (REL_OBJ_RESPONSIBLE, )
    verbose_name  = _(u'Responsibles')
    template_name = 'opportunities/templatetags/block_responsibles.html'

    def detailview_display(self, context):
        global _contact_ct_id

        opp = context['object']

        if not _contact_ct_id:
            _contact_ct_id = ContentType.objects.get_for_model(Contact).id

        return self._render(self.get_block_template_context(context,
                                                            opp.get_responsibles(),
                                                            update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, opp.pk),
                                                            predicate_id=REL_OBJ_RESPONSIBLE,
                                                            ct_id=_contact_ct_id))


class QuotesBlock(QuerysetBlock):
    id_           = QuerysetBlock.generate_id('opportunities', 'quotes')
    dependencies  = (Relation,)
    relation_type_deps = (REL_OBJ_LINKED_QUOTE, )
    verbose_name  = _(u"Quotes linked to the opportunity")
    template_name = 'opportunities/templatetags/block_quotes.html'

    def __init__(self, *args, **kwargs):
        super(QuotesBlock, self).__init__(*args, **kwargs)

        self._quote_ct_id = None

    def detailview_display(self, context):
        opp = context['object']

        if not self._quote_ct_id:
            self._quote_ct_id = ContentType.objects.get_for_model(Quote).id

        return self._render(self.get_block_template_context(context,
                                                            opp.get_quotes(),
                                                            update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, opp.pk),
                                                            predicate_id=REL_OBJ_LINKED_QUOTE,
                                                            ct_id=self._quote_ct_id,
                                                            current_quote_id=opp.get_current_quote_id()))


class SalesOrdersBlock(QuerysetBlock):
    id_           = QuerysetBlock.generate_id('opportunities', 'sales_orders')
    dependencies  = (Relation,)
    relation_type_deps = (REL_OBJ_LINKED_SALESORDER, )
    verbose_name  = _(u"Salesorders linked to the opportunity")
    template_name = 'opportunities/templatetags/block_sales_orders.html'

    def __init__(self, *args, **kwargs):
        super(SalesOrdersBlock, self).__init__(*args, **kwargs)

        self._salesorder_ct_id = None

    def detailview_display(self, context):
        opp = context['object']

        if not self._salesorder_ct_id:
            self._salesorder_ct_id = ContentType.objects.get_for_model(SalesOrder).id

        block_context = self.get_block_template_context(context, opp.get_salesorder(),
                                                        update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, opp.pk),
                                                        predicate_id=REL_OBJ_LINKED_SALESORDER,
                                                        ct_id=self._salesorder_ct_id)

        return self._render(block_context)


class InvoicesBlock(QuerysetBlock):
    id_           = QuerysetBlock.generate_id('opportunities', 'invoices')
    dependencies  = (Relation,)
    relation_type_deps = (REL_OBJ_LINKED_INVOICE, )
    verbose_name  = _(u"Invoices linked to the opportunity")
    template_name = 'opportunities/templatetags/block_invoices.html'

    def __init__(self, *args, **kwargs):
        super(InvoicesBlock, self).__init__(*args, **kwargs)

        self._invoice_ct_id = None

    def detailview_display(self, context):
        opp = context['object']

        if not self._invoice_ct_id:
            self._invoice_ct_id = ContentType.objects.get_for_model(Invoice).id

        return self._render(self.get_block_template_context(context,
                                                            opp.get_invoices(),
                                                            update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, opp.pk),
                                                            predicate_id=REL_OBJ_LINKED_INVOICE,
                                                            ct_id=self._invoice_ct_id))

class TargetOrganisationsBlock(QuerysetBlock):
    id_           = QuerysetBlock.generate_id('opportunities', 'target_organisations')
    dependencies  = (Relation,) #Organisation
    relation_type_deps = (REL_OBJ_TARGETS_ORGA, )
    verbose_name  = _(u"Opportunities which target the organisation")
    template_name = 'opportunities/templatetags/block_target_orga.html'

    def detailview_display(self, context):
        orga = context['object']

        return self._render(self.get_block_template_context(context,
                                                            Opportunity.objects.filter(relations__object_entity=orga.id, relations__type=REL_SUB_TARGETS_ORGA),
                                                            update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, orga.pk),
                                                            predicate_id=REL_OBJ_TARGETS_ORGA,
                                                            ct=ContentType.objects.get_for_model(Opportunity),
                                                            ))

linked_contacts_block     = LinkedContactsBlock()
linked_products_block     = LinkedProductsBlock()
linked_services_block     = LinkedServicesBlock()
responsibles_block        = ResponsiblesBlock()
quotes_block              = QuotesBlock()
sales_orders_block        = SalesOrdersBlock()
invoices_block            = InvoicesBlock()
target_organisation_block = TargetOrganisationsBlock()
