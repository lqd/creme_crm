# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2017  Hybird
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

from future_builtins import filter, map
from collections import defaultdict
import logging, warnings

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.core.urlresolvers import reverse
from django.db.models import Model
from django.template.loader import get_template
from django.utils.translation import ugettext_lazy as _, ugettext

from ..core.entity_cell import EntityCellRegularField
from ..models import (Relation, RelationBlockItem, CremeEntity,
        InstanceBlockConfigItem, CustomBlockConfigItem, BlockState)


logger = logging.getLogger(__name__)


def list4url(list_):
    "Special url list-to-string function"
    return ','.join(str(i) for i in list_)


def str2list(string):
    "'1,2,3'  -> [1, 2, 3]"
    return [int(i) for i in string.split(',') if i.isdigit()]


class _BrickContext(object):
    def __repr__(self):
        return '<BrickContext>'

    def as_dict(self):
        return {}

    @classmethod
    def from_dict(cls, data):
        instance = cls()

        for k, v in data.iteritems():
            setattr(instance, k, v)

        return instance

    def update(self, template_context):
        """Overload me (see _PaginatedBrickContext, _QuerysetBrickContext)"""
        return False


class Brick(object):
    """ A block of information.
    Blocks can be displayed on (see creme_core.templatetags.creme_block):
        - a detail-view (and so are related to a CremeEntity),
        - a portal (related to the content types of an app)
        - the homepage - ie the portal of creme_core (related to all the apps).

    A Block can be directly displayed on a page (this is the only solution for
    pages that are not a detail-view, a portal or the home). But the better
    solution is to use the configuration system (see creme_core.models.blocks
    & creme_config).

    Reloading after a change (deleting, adding, updating, etc...) in the block
    can be done with ajax if the correct view is set : for this, each block has
    a unique id in a page.

    When you inherit the Block class, you have to define these optionnal methods
    to allow the different possibility of display:

    def detailview_display(self, context):
        return 'VOID BLOCK FOR DETAILVIEW: %s' % self.verbose_name

    def portal_display(self, context, ct_ids):
        return 'VOID BLOCK FOR PORTAL: %s' % self.verbose_name

    def home_display(self, context):
        return 'VOID BLOCK FOR HOME: %s' % self.verbose_name
    """
    id_           = None               # Overload with an unicode object ; use generate_id()
    dependencies  = ()                 # List of the models on which the block depends
                                       #   (ie: generally the block displays these models) ;
                                       #   it also can be the '*' string, which is a wildcard meaning
                                       #   'All models used in the page'.
    relation_type_deps = ()            # List of id of RelationType objects on which the block depends ;
                                       #   only used for Blocks which have 'Relation' in their dependencies
    read_only     = False              # 'True' means : the block never causes a DB change on its dependencies models.
                                       #   ---> so when this is reload (eg: to change the pagination), it does
                                       #   not causes the dependant blocks to be reload (but it is still
                                       #   reload when the dependant blocks are reload of course).
    verbose_name  = 'BLOCK'            # Used in the user configuration
                                       #   (see BlockDetailviewLocation/BlockPortalLocation)
    template_name = 'OVERLOAD_ME.html' # Used to render the block of course
    context_class = _BrickContext      # Store the context in the session.
    configurable  = True               # True: the Block can be add/removed to detailview/portal by
                                       #   configuration (see creme_config)
    target_ctypes = ()                 # Tuple of CremeEntity classes that can have this type of block.
                                       #  Empty tuple means that all types are ok. eg: (Contact, Organisation)
    target_apps = ()                   # Tuple of name of the Apps that can have this Block on their portal.
                                       #   Empty tuple means that all Apps are ok. eg: ('persons',)

    GENERIC_HAT_BRICK_ID = 'hatbrick'

    def __init__(self):
        self._reloading_info = None

    @property
    def reloading_info(self):
        return self._reloading_info

    @reloading_info.setter
    def reloading_info(self, info):
        """Setter for reloading info.
        @param info: data which will be sent at reload. Must be serializable to JSON.
        """
        self._reloading_info = info

    @staticmethod
    def generate_id(app_name, name):  # TODO: rename _generate_id ?
        return u'block_%s-%s' % (app_name, name)

    @classmethod
    def _generate_hat_id(cls, app_name, name):
        return u'%s-%s-%s' % (cls.GENERIC_HAT_BRICK_ID, app_name, name)

    def _render(self, template_context):
        return get_template(self.template_name).render(template_context)

    def _simple_detailview_display(self, context):
        """Helper method to build a basic detailview_display() method for classes that inherit Block."""
        # return self._render(self.get_block_template_context(
        return self._render(self.get_template_context(
                                context,
                                # update_url='/creme_core/blocks/reload/%s/%s/' % (
                                #                     self.id_,
                                #                     context['object'].pk,
                                #                 ),
                                update_url=reverse('creme_core__reload_detailview_blocks',
                                                   args=(self.id_, context['object'].pk),
                                                  ),
                           ))

    def _iter_dependencies_info(self):
        for dep in self.dependencies:
            if isinstance(dep, type) and issubclass(dep, Model):
                if dep == Relation:
                    for rtype_id in self.relation_type_deps:
                        yield 'creme_core.relation.' + rtype_id
                else:
                    meta = dep._meta
                    yield '%s.%s' % (meta.app_label, meta.model_name)
            else:
                yield unicode(dep)

    def _build_template_context(self, context, block_name, block_context, **extra_kwargs):
        context['block_name'] = context['brick_id'] = block_name  # TODO: deprecate 'block_name'.
        context['state'] = BricksManager.get(context).get_state(self.id_, context['user'])
        # context['dependencies'] = ','.join(self._iter_dependencies_info())
        context['dependencies'] = list(self._iter_dependencies_info())
        context['reloading_info'] = self._reloading_info
        context['read_only'] = self.read_only

        context.update(extra_kwargs)

        return context

    def get_block_template_context(self, *args, **kwargs):
        warnings.warn('Brick.get_block_template_context() is deprecated ; use get_template_context() instead.',
                      DeprecationWarning
                     )
        return self.get_template_context(*args, **kwargs)

    def get_template_context(self, context, update_url='', **extra_kwargs):
        """ Build the brick template context.
        @param context: Template context (contains 'request' etc...).
        @param update_url: String containing url to reload this block with ajax.
                           USELESS with new brick system (should be deprecated in creme1.8).
        """
        brick_id = self.id_
        request = context['request']
        base_url = request.GET.get('base_url', request.path)
        session = request.session

        try:
            # serialized_context = session['blockcontexts_manager'][base_url][brick_id]
            serialized_context = session['brickcontexts_manager'][base_url][brick_id]
        except KeyError:
            brick_context = self.context_class()
        else:
            brick_context = self.context_class.from_dict(serialized_context)

        template_context = self._build_template_context(context, brick_id, brick_context,
                                                        base_url=base_url,  # TODO: remove in creme 1.8
                                                        update_url=update_url,  # TODO: remove in creme 1.8
                                                        **extra_kwargs
                                                       )

        # if not BlocksManager.get(context).block_is_registered(self):
        # NB:  not 'assert' (it causes problems with bricks in inner popups)
        if not BricksManager.get(context).brick_is_registered(self):
            logger.debug('Not registered brick: %s', self.id_)

        if brick_context.update(template_context):
            # session.setdefault('blockcontexts_manager', {}) \
            session.setdefault('brickcontexts_manager', {}) \
                   .setdefault(base_url, {}) \
                   [brick_id] = brick_context.as_dict()

            request.session.modified = True

        return template_context


class SimpleBrick(Brick):
     detailview_display = Brick._simple_detailview_display


class _PaginatedBrickContext(_BrickContext):
    __slots__ = ('page',)

    def __init__(self):
        self.page = 1

    def __repr__(self):
        return '<PaginatedBrickContext: page=%s>' % self.page

    def as_dict(self):
        return {'page': self.page}

    def update(self, template_context):
        page = template_context['page'].number

        if self.page != page:
            modified = True
            self.page = page
        else:
            modified = False

        return modified


class PaginatedBrick(Brick):
    """This king of Block is generally represented by a paginated table.
    Ajax changes management is used to change page.
    """
    context_class = _PaginatedBrickContext
    page_size     = settings.BLOCK_SIZE  # Number of items in the page

    def _build_template_context(self, context, block_name, block_context, **extra_kwargs):
        request = context['request']
        objects = extra_kwargs.pop('objects')

        page_index = request.GET.get('%s_page' % block_name)
        if page_index is not None:
            try:
                page_index = int(page_index)
            except ValueError:
                logger.debug('Invalid page number for block %s: %s', block_name, page_index)
                page_index = 1
        else:
            page_index = block_context.page

        paginator = Paginator(objects, self.page_size)

        try:
            page = paginator.page(page_index)
        except (EmptyPage, InvalidPage):
            page = paginator.page(paginator.num_pages)

        return super(PaginatedBrick, self)._build_template_context(context, block_name, block_context,
                                                                   page=page, **extra_kwargs
                                                                  )

    def get_block_template_context(self, *args, **kwargs):
        warnings.warn('PaginatedBrick.get_block_template_context() is deprecated ; use get_template_context() instead.',
                      DeprecationWarning
                     )
        return self.get_template_context(*args, **kwargs)

    def get_template_context(self, context, objects, update_url='', **extra_kwargs):
        """@param objects Set of objects to display in the block."""
        return Brick.get_template_context(self, context, update_url=update_url, objects=objects, **extra_kwargs)


class _QuerysetBrickContext(_PaginatedBrickContext):
    __slots__ = ('page', '_order_by')

    def __init__(self):
        super(_QuerysetBrickContext, self).__init__()  # *args **kwargs ??
        self._order_by = ''

    def __repr__(self):
        return '<QuerysetBlockContext: page=%s order_by=%s>' % (self.page, self._order_by)

    def as_dict(self):
        d = super(_QuerysetBrickContext, self).as_dict()
        d['_order_by'] = self._order_by

        return d

    def get_order_by(self, order_by):
        _order_by = self._order_by

        if _order_by:
            return _order_by

        return order_by

    def update(self, template_context):
        modified = super(_QuerysetBrickContext, self).update(template_context)
        order_by = template_context['order_by']

        if self._order_by != order_by:
            modified = True
            self._order_by = order_by

        return modified


class QuerysetBrick(PaginatedBrick):
    """In this brick, displayed objects are stored in a queryset.
    It allows to order objects by one of its columns (which can change): order
    changes are done with ajax of course.
    """
    context_class = _QuerysetBrickContext
    order_by      = ''  # Default order_by value ; '' means no order_by

    def _build_template_context(self, context, block_name, block_context, **extra_kwargs):
        request = context['request']
        order_by = self.order_by
        objects = extra_kwargs['objects']

        if order_by:
            request_order_by = request.GET.get('%s_order' % block_name)

            if request_order_by is not None:
                order_by = request_order_by  # TODO: test if order_by is valid (field name) ????
            else:
                order_by = block_context.get_order_by(order_by)

            extra_kwargs['objects'] = objects.order_by(order_by)

        return super(QuerysetBrick, self)._build_template_context(
                context, block_name, block_context,
                objects_ctype=ContentType.objects.get_for_model(objects.model),
                order_by=order_by,
                **extra_kwargs
        )

    def get_block_template_context(self, *args, **kwargs):
        warnings.warn('QuerysetBrick.get_block_template_context() is deprecated ; use get_template_context() instead.',
                      DeprecationWarning
                     )
        return self.get_template_context(*args, **kwargs)

    def get_template_context(self, context, queryset, update_url='', **extra_kwargs):
        """@param queryset Set of objects to display in the block."""
        return PaginatedBrick.get_template_context(self, context, objects=queryset,
                                                   update_url=update_url,
                                                   **extra_kwargs
                                                  )


class EntityBrick(Brick):
    verbose_name  = _(u'Information on the entity (generic)')
    template_name = 'creme_core/bricks/generic/entity.html'

    BASE_FIELDS = {'created', 'modified', 'user'}

    def _get_cells(self, entity, context):
        model = entity.__class__
        BASE_FIELDS = self.BASE_FIELDS
        is_hidden = context['fields_configs'].get_4_model(model).is_field_hidden

        def build_cell(field_name):
            cell = EntityCellRegularField.build(model=model, name=field_name)
            cell.is_base_field = field_name in BASE_FIELDS

            return cell

        return [build_cell(field.name)
                    for field in model._meta.fields
                        if field.get_tag('viewable') and not is_hidden(field)
               ]

    def _get_title(self, entity, context):
        return ugettext(u'Information «{model}»').format(model=entity.__class__._meta.verbose_name)

    def detailview_display(self, context):
        entity = context['object']

        return self._render(self.get_template_context(
                    context,
                    title=self._get_title(entity, context),
                    cells=self._get_cells(entity, context),
        ))


class SpecificRelationsBrick(QuerysetBrick):
    dependencies  = (Relation,)  # NB: (Relation, CremeEntity) but useless
    order_by      = 'type'
    verbose_name  = _(u'Relationships')
    # template_name = 'creme_core/templatetags/block_specific_relations.html'
    template_name = 'creme_core/bricks/specific-relations.html'

    def __init__(self, relationblock_item):
        "@param relationblock_item Instance of RelationBlockItem"
        super(SpecificRelationsBrick, self).__init__()
        self.id_ = relationblock_item.block_id
        self.config_item = relationblock_item

        rtype = relationblock_item.relation_type
        self.relation_type_deps = (rtype.id,)
        self.verbose_name = ugettext(u'Relationship block: «%s»') % rtype.predicate

    @staticmethod
    def generate_id(app_name, name):
        return u'specificblock_%s-%s' % (app_name, name)

    @staticmethod
    def id_is_specific(id_):
        return id_.startswith(u'specificblock_')

    def detailview_display(self, context):
        entity = context['object']
        config_item = self.config_item
        relation_type = config_item.relation_type
        # btc = self.get_block_template_context(
        btc = self.get_template_context(
                    context,
                    entity.relations.filter(type=relation_type)
                                    .select_related('type', 'object_entity'),
                    # update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, entity.pk),
                    update_url=reverse('creme_core__reload_detailview_blocks',
                                       args=(self.id_, entity.pk),
                                      ),
                    relation_type=relation_type,
                   )
        relations = btc['page'].object_list
        entities_by_ct = defaultdict(list)

        Relation.populate_real_object_entities(relations)  # DB optimisation

        for relation in relations:
            entity = relation.object_entity.get_real_entity()
            entity.srb_relation_cache = relation
            entities_by_ct[entity.entity_type_id].append(entity)

        groups = []  # List of tuples (entities_with_same_ct, headerfilter_items)
        unconfigured_group = []  # Entities that do not have a customised columns setting
        colspan = 1  # Unconfigured_group has one column
        get_ct = ContentType.objects.get_for_id

        for ct_id, entities in entities_by_ct.iteritems():
            cells = config_item.get_cells(get_ct(ct_id))

            if cells:
                groups.append((entities, cells))
                colspan = max(colspan, len(cells))
            else:
                unconfigured_group.extend(entities)

        groups.append((unconfigured_group, None))  # 'unconfigured_group' must be at the end

        btc['groups'] = groups
        btc['colspan'] = colspan + 1  # Add one because of 'Unlink' column  # TODO: remove in creme1.8

        return self._render(btc)


class CustomBrick(Brick):
    """Brick that can be customised by the user to display information of an entity.
    It can display regular, custom & function fields, relationships... (see HeaderFilter & EntityCells)
    """
    # template_name = 'creme_core/templatetags/block_custom.html'
    template_name = 'creme_core/bricks/custom.html'

    def __init__(self, id_, customblock_conf_item):
        "@param customblock_conf_item Instance of CustomBlockConfigItem"
        super(CustomBrick, self).__init__()
        self.id_ = id_
        self.dependencies = (customblock_conf_item.content_type.model_class(),)  # TODO: other model (FK, M2M, Relation)
        # self.relation_type_deps = () #TODO: if cell is EntityCellRelation
        self.verbose_name = customblock_conf_item.name
        self.config_item = customblock_conf_item

    def detailview_display(self, context):
        entity = context['object']

        # return self._render(self.get_block_template_context(
        return self._render(self.get_template_context(
                    context,
                    # update_url='/creme_core/blocks/reload/%s/%s/' % (self.id_, entity.pk),
                    update_url=reverse('creme_core__reload_detailview_blocks',
                                       args=(self.id_, entity.pk),
                                      ),
                    config_item=self.config_item,
        ))


class BricksManager(object):
    """The bricks of a page are registered in order to regroup the query to get their states.

    Documentation for DEPRECATED features:
    Using to solve the blocks dependencies problem in a page.
    Blocks can depends on the same model : updating one block involves to update
    the blocks that depends on the same than it.
    """
    var_name = 'blocks_manager'  # TODO: rename

    class Error(Exception):
        pass

    def __init__(self):
        # self._blocks = []
        self._bricks = []
        self._dependencies_map = None
        # self._blocks_groups = defaultdict(list)
        self._bricks_groups = defaultdict(list)
        self._used_relationtypes = None
        self._state_cache = None

    # def add_group(self, group_name, *blocks):
    def add_group(self, group_name, *bricks):
        if self._dependencies_map is not None:
            raise BricksManager.Error("Can't add brick to manager after dependence resolution is done.")

        group = self._bricks_groups[group_name]
        if group:
            raise BricksManager.Error("This brick's group name already exists: %s" % group_name)

        self._bricks.extend(bricks)
        group.extend(bricks)

    def brick_is_registered(self, brick):
        brick_id = brick.id_
        return any(b.id_ == brick_id for b in self._bricks)

    def block_is_registered(self, block):
        warnings.warn('BlocksManager.block_is_registered() is deprecated ; use brick_is_registered() instead.',
                      DeprecationWarning
                     )
        return self.brick_is_registered(block)

    def _build_dependencies_map(self):
        dep_map = self._dependencies_map

        if dep_map is None:
            self._dependencies_map = dep_map = defaultdict(list)
            wilcarded_blocks = []

            for block in self._bricks:
                dependencies = block.dependencies

                if dependencies == '*':
                    wilcarded_blocks.append(block)
                else:
                    for dep in dependencies:
                        dep_map[dep].append(block)

            if wilcarded_blocks:
                for dep_blocks in dep_map.itervalues():
                    dep_blocks.extend(wilcarded_blocks)

        return dep_map

    def _get_dependencies_ids(self, block):
        # warnings.warn('BlocksManager._get_dependencies_ids() is deprecated.', DeprecationWarning)  TODO: in 1.8
        dep_map = self._build_dependencies_map()
        depblocks_ids = set()

        if not block.read_only:
            id_ = block.id_

            dependencies = block.dependencies
            if dependencies == '*':
                dependencies = dep_map.keys()

            for dep in dependencies:
                for other_block in dep_map[dep]:
                    if other_block.id_ == id_:
                        continue

                    if dep == Relation:
                        if other_block.dependencies != '*' and \
                           not set(block.relation_type_deps) & set(other_block.relation_type_deps):
                            continue

                    depblocks_ids.add(other_block.id_)

        return depblocks_ids

    @staticmethod
    def get(context):
        return context[BricksManager.var_name]  # Will raise exception if not created: OK

    def get_remaining_groups(self):
        return self._bricks_groups.keys()

    def get_dependencies_map(self):
        # warnings.warn('BlocksManager.get_dependencies_map() is deprecated.', DeprecationWarning)  TODO: in 1.8
        get_dep = self._get_dependencies_ids
        return {block.id_: get_dep(block) for block in self._bricks}

    # def get_state(self, block_id, user):
    def get_state(self, brick_id, user):
        "Get the state for a brick and fill a cache to avoid multiple SQL requests"
        _state_cache = self._state_cache
        if not _state_cache:
            _state_cache = self._state_cache = BlockState.get_for_brick_ids([block.id_ for block in self._bricks], user)

        state = _state_cache.get(brick_id)
        if state is None:
            state = self._state_cache[brick_id] = BlockState.get_for_brick_id(brick_id, user)
            logger.warn("State not set in cache for '%s'" % brick_id)

        return state

    def pop_group(self, group_name):
        return self._bricks_groups.pop(group_name)

    @property
    def used_relationtypes_ids(self):
        if self._used_relationtypes is None:
            self._used_relationtypes = {rt_id for block in self._build_dependencies_map()[Relation]
                                            for rt_id in block.relation_type_deps
                                       }

        return self._used_relationtypes

    @used_relationtypes_ids.setter
    def used_relationtypes_ids(self, relationtypes_ids):
        "@param relation_type_deps Sequence of RelationType objects' ids"
        self._used_relationtypes = set(relationtypes_ids)


class _BrickRegistry(object):
    """Use to retrieve a Brick by its id.
    Many services (like reloading views) need your Bricks to be registered in.
    """
    class RegistrationError(Exception):
        pass

    def __init__(self):
        # self._blocks = {}
        self._brick_classes = {}
        # self._object_blocks = {}
        self._hat_brick_classes = defaultdict(dict)
        self._object_brick_classes = {}
        # self._instance_block_classes = {}
        self._instance_brick_classes = {}
        self._invalid_models = set()

    def register(self, *brick_classes):
        setdefault = self._brick_classes.setdefault

        for brick_cls in brick_classes:
            if isinstance(brick_cls, Brick):
                warnings.warn('_BlockRegistry.register(): registered brick instance is deprecated ;'
                              'register brick class instead (brick ID=%s)' % brick_cls.id_,
                              DeprecationWarning
                             )
                brick_cls = brick_cls.__class__

            if setdefault(brick_cls.id_, brick_cls) is not brick_cls:
                raise _BrickRegistry.RegistrationError("Duplicated brick's id: %s" % brick_cls.id_)

    def register_4_instance(self, *brick_classes):  # TODO: factorise
        setdefault = self._instance_brick_classes.setdefault

        for brick_cls in brick_classes:
            if setdefault(brick_cls.id_, brick_cls) is not brick_cls:
                raise _BrickRegistry.RegistrationError("Duplicated brick's id: %s" % brick_cls.id_)

    def register_invalid_models(self, *models):
        """Register some models which cannot have a bricks configuration for
        their detail-views (eg: they have no detail-view, or they are not 'classical' ones).
        @param models: Classes inheriting CremeEntity.
        """
        add = self._invalid_models.add

        for model in models:
            assert issubclass(model, CremeEntity)
            add(model)

    # def register_4_model(self, model, block):
    def register_4_model(self, model, brick_cls):  # TODO: had an 'overload' arg ??
        if isinstance(brick_cls, Brick):
            warnings.warn('_BlockRegistry.register_4_model(): registered brick instance is deprecated ;'
                          'register brick class instead (model=%s)' % model,
                          DeprecationWarning
                         )
            brick_cls = brick_cls.__class__

        if brick_cls.id_ is not None:
            warnings.warn('_BlockRegistry.register_4_model(): brick for model=%s should have '
                          'an id_ == None (currently: %s)' % ( model, brick_cls.id_),
                          DeprecationWarning
                         )

        # brick_cls.id_ = self._generate_modelblock_id(model)
        #
        # if not brick_cls.dependencies:
        #     brick_cls.dependencies = (model,)

        # NB: the key is the class, not the ContentType.id because it can cause
        # some inconsistencies in DB problem in unit tests (contenttypes cache bug with tests ??)
        self._object_brick_classes[model] = brick_cls

    def register_hat(self, model, main_brick_cls=None, secondary_brick_classes=()):
        brick_classes = self._hat_brick_classes[model]

        if main_brick_cls is not None:
            assert issubclass(main_brick_cls, Brick)

            if main_brick_cls.id_ is not None:
                raise _BrickRegistry.RegistrationError('Main hat brick for model=%s must be None (currently: %s)' % (
                                                            model, main_brick_cls.id_,
                                                        )
                                                       )

            brick_classes[''] = main_brick_cls

        for brick_cls in secondary_brick_classes:
            assert issubclass(brick_cls, Brick)

            brick_id = brick_cls.id_

            if not brick_id or not brick_id.startswith(Brick.GENERIC_HAT_BRICK_ID + '-'):
                raise _BrickRegistry.RegistrationError('Secondary hat brick for model=%s must have an id_ '
                                                       'generated by Block._generate_hat_id() (%s)' % (
                                                            model, brick_cls,
                                                        )
                                                      )

            if brick_id in brick_classes:
                raise _BrickRegistry.RegistrationError("Duplicated hat brick's id_: %s" % brick_id)

            brick_classes[brick_id] = brick_cls

    # def _generate_modelblock_id(self, model):
    @staticmethod
    def _generate_modelbrick_id(model):
        meta = model._meta
        return u'modelblock_%s-%s' % (meta.app_label, meta.model_name)

    # def __getitem__(self, block_id):
    def __getitem__(self, brick_id):
        # return self._brick_classes[block_id]
        return self._brick_classes[brick_id]

    def __iter__(self):
        return self._brick_classes.iteritems()

    def get_brick_4_instance(self, ibi, entity=None):
        """Get a Block instance corresponding to a InstanceBlockConfigItem.
        @param ibi InstanceBlockConfigItem instance.
        @param entity CremeEntity instance if your Block has to be displayed on its detailview.
        @return Block instance.
        """
        brick_id = ibi.block_id
        brick_class = self._instance_brick_classes.get(InstanceBlockConfigItem.get_base_id(brick_id))

        if brick_class is None:
            logger.warning('Brick class seems deprecated: %s', brick_id)

            brick = Brick()
            brick.verbose_name = '??'
            brick.errors = [_(u'Unknown type of block (bad uninstall ?)')]
        else:
            brick = brick_class(ibi)
            brick.id_ = brick_id

            if entity:
                # When an InstanceBlock is on a detailview of a entity, the content
                # of this brick depends (generally) of this entity, so we have to
                # complete the dependencies.
                model = entity.__class__
                if model not in brick.dependencies:
                    brick.dependencies += (model,)

        return brick

    def get_block_4_instance(self, ibi, entity=None):
        warnings.warn('_BlockRegistry.get_block_4_instance() is deprecated ; use get_brick_4_instance() instead.',
                      DeprecationWarning
                     )
        return self.get_brick_4_instance(ibi, entity)

    def get_bricks(self, brick_ids, entity=None):
        """Bricks type can be SpecificRelationsBlock/InstanceBlockConfigItem:
        in this case, they are not really registered, but created on the fly.
        @param brick_ids: Sequence of id of bricks
        @param entity: if the bricks are displayed of the detail-view of an entity,
                       it should be given.
        """
        specific_ids = list(filter(SpecificRelationsBrick.id_is_specific, brick_ids))
        instance_ids = list(filter(InstanceBlockConfigItem.id_is_specific, brick_ids))
        custom_ids   = list(filter(None, map(CustomBlockConfigItem.id_from_brick_id, brick_ids)))

        relation_bricks_items = {rbi.block_id: rbi
                                     for rbi in RelationBlockItem.objects.filter(block_id__in=specific_ids)
                                } if specific_ids else {}
        instance_bricks_items = {ibi.block_id: ibi
                                     for ibi in InstanceBlockConfigItem.objects.filter(block_id__in=instance_ids)
                                } if instance_ids else {}
        custom_bricks_items = {cbci.generate_id(): cbci
                                   for cbci in CustomBlockConfigItem.objects.filter(id__in=custom_ids)
                              } if custom_ids else {}

        for id_ in brick_ids:
            rbi = relation_bricks_items.get(id_)
            if rbi:
                yield SpecificRelationsBrick(rbi)
                continue

            ibi = instance_bricks_items.get(id_)
            if ibi:
                yield self.get_brick_4_instance(ibi, entity)
                continue

            cbci = custom_bricks_items.get(id_)
            if cbci:
                yield CustomBrick(id_, cbci)
                continue

            if id_.startswith('modelblock_'):  # TODO: constant ?
                yield self.get_brick_4_object(ContentType.objects
                                                         .get_by_natural_key(*id_[len('modelblock_'):].split('-'))
                                             )
                continue

            if id_.startswith(Brick.GENERIC_HAT_BRICK_ID):
                if entity is None:
                    logger.warning('Header brick without entity ?!')
                else:
                    model = entity.__class__

                    if id_ == Brick.GENERIC_HAT_BRICK_ID:
                        yield self.get_generic_hat_brick(model)
                    else:
                        brick_cls = self._hat_brick_classes[model].get(id_)
                        if brick_cls is None:
                            logger.warning('Invalid hat brick ID: %s', id_)
                            yield self.get_generic_hat_brick(model)
                        else:
                            yield brick_cls()

                continue

            brick_cls = self._brick_classes.get(id_)
            if brick_cls is None:
                logger.warning('Brick seems deprecated: %s', id_)
                yield Brick()
            else:
                yield brick_cls()

    def get_blocks(self, block_ids, entity=None):
        warnings.warn('_BlockRegistry.get_blocks() is deprecated ; '
                      'use get_bricks() instead (beware it is a generator).',
                      DeprecationWarning
                     )

        specific_ids = list(filter(SpecificRelationsBrick.id_is_specific, block_ids))
        instance_ids = list(filter(InstanceBlockConfigItem.id_is_specific, block_ids))
        custom_ids   = list(filter(None, map(CustomBlockConfigItem.id_from_block_id, block_ids)))

        relation_blocks_items = {rbi.block_id: rbi
                                    for rbi in RelationBlockItem.objects.filter(block_id__in=specific_ids)
                                } if specific_ids else {}
        instance_blocks_items = {ibi.block_id: ibi
                                    for ibi in InstanceBlockConfigItem.objects.filter(block_id__in=instance_ids)
                                } if instance_ids else {}
        custom_blocks_items = {cbci.generate_id(): cbci
                                    for cbci in CustomBlockConfigItem.objects.filter(id__in=custom_ids)
                              } if custom_ids else {}

        blocks = []

        for id_ in block_ids:
            rbi = relation_blocks_items.get(id_)
            ibi = instance_blocks_items.get(id_)
            cbci = custom_blocks_items.get(id_)

            if rbi:
                block = SpecificRelationsBrick(rbi)
            elif ibi:
                block = self.get_block_4_instance(ibi, entity)
            elif cbci:
                block = CustomBrick(id_, cbci)
            elif id_.startswith('modelblock_'):
                block = self.get_block_4_object(ContentType.objects.get_by_natural_key(*id_[len('modelblock_'):].split('-')))
            else:
                # block = self._blocks.get(id_)
                #
                # if block is None:
                #     logger.warning('Block seems deprecated: %s', id_)
                #     block = Block()
                brick_cls = self._brick_classes.get(id_)

                if brick_cls is None:
                    logger.warning('Brick seems deprecated: %s', id_)
                    block = Brick()
                else:
                    block = brick_cls()

            blocks.append(block)

        return blocks

    def get_brick_4_object(self, obj_or_ct):
        """Return the Brick that displays fields for a CremeEntity instance.
        @param obj_or_ct: Model (class inheriting CremeEntity), or ContentType instance
                          representing this model, or instance of this model.
        """
        model = obj_or_ct.__class__ if isinstance(obj_or_ct, CremeEntity) else \
                obj_or_ct.model_class() if isinstance(obj_or_ct, ContentType) else \
                obj_or_ct
        brick_cls = self._object_brick_classes.get(model)

        if brick_cls is None:
            brick = EntityBrick()
            # brick.id_ = self._generate_modelblock_id(model)
            brick.dependencies = (model,)  # TODO: what about FK, M2M ?
            # brick.template_name = 'creme_core/templatetags/block_object.html'
            # brick.template_name = 'creme_core/bricks/generic/object.html'
            # brick.verbose_name = _(u'Information on the entity')

            # self._object_brick_classes[model] = brick
        else:
            brick = brick_cls()

            if not brick.dependencies:
                # TODO: warning ??
                brick.dependencies = (model,)  # TODO: what about FK, M2M ?

            if brick.verbose_name is Brick.verbose_name:
                # TODO: warning ??
                brick.verbose_name = _(u'Information on the entity')

        brick.id_ = self._generate_modelbrick_id(model)

        return brick

    def get_block_4_object(self, obj_or_ct):
        warnings.warn('_BlockRegistry.get_block_4_object() is deprecated ; use get_brick_4_object() instead.',
                      DeprecationWarning
                     )
        return self.get_brick_4_object(obj_or_ct)

    def get_generic_hat_brick(self, model):
        brick_cls = self._hat_brick_classes[model].get('')

        if brick_cls is None:
            brick = SimpleBrick()
            brick.dependencies = (model,)  # TODO: what about FK, M2M ?
            brick.template_name = 'creme_core/bricks/generic/hat-bar.html'
        else:
            brick = brick_cls()

            if not brick.dependencies:
                brick.dependencies = (model,)  # TODO: what about FK, M2M ?

        brick.id_ = Brick.GENERIC_HAT_BRICK_ID
        brick.verbose_name = _(u'Title bar')

        return brick

    def get_compatible_bricks(self, model=None):
        """Returns the list of registered bricks that are configurable and compatible with the given ContentType.
        @param model: Constraint on a CremeEntity class ;
                      None means bricks must be compatible with all kind of CremeEntity.
        """
        for brick_cls in self._brick_classes.itervalues():
            brick = brick_cls()

            if brick.configurable and hasattr(brick, 'detailview_display') \
               and (not brick.target_ctypes or model in brick.target_ctypes):
                yield brick

        # TODO: filter compatible relation types
        #       (problem the constraints can change after we config blocks...
        #        => keep only if constraint are broken by existing relationships ?)
        for rbi in RelationBlockItem.objects.all():  # TODO: select_related('relation_type') ??
            yield SpecificRelationsBrick(rbi)

        for ibi in InstanceBlockConfigItem.objects.all():
            brick = self.get_brick_4_instance(ibi)

            if hasattr(brick, 'detailview_display') \
                    and (not brick.target_ctypes or model in brick.target_ctypes):
                yield brick

        if model:
            yield self.get_brick_4_object(model)

            for cbci in CustomBlockConfigItem.objects.filter(content_type=ContentType.objects.get_for_model(model)):
                yield CustomBrick(cbci.generate_id(), cbci)

    def get_compatible_blocks(self, model=None):
        warnings.warn('_BlockRegistry.get_compatible_blocks() is deprecated ; '
                      'use get_compatible_bricks() instead '
                      '(beware: it returns object-brick too).',
                      DeprecationWarning
                     )

        for brick_cls in self._brick_classes.itervalues():
            block = brick_cls()

            if block.configurable and hasattr(block, 'detailview_display') \
               and (not block.target_ctypes or model in block.target_ctypes):
                yield block

        for rbi in RelationBlockItem.objects.all():
            yield SpecificRelationsBrick(rbi)

        for ibi in InstanceBlockConfigItem.objects.all():
            block = self.get_block_4_instance(ibi)

            if hasattr(block, 'detailview_display') \
                    and (not block.target_ctypes or model in block.target_ctypes):
                yield block

        if model:
            for cbci in CustomBlockConfigItem.objects.filter(content_type=ContentType.objects.get_for_model(model)):
                yield CustomBrick(cbci.generate_id(), cbci)

    def get_compatible_hat_bricks(self, model):
        yield self.get_generic_hat_brick(model)

        for brick_id, brick_cls in self._hat_brick_classes[model].iteritems():
            if brick_id:  # Only generic hat brick's ID is empty
                yield brick_cls()

    # TODO: deprecate/delete in 1.8 (+ add a method get_compatible_home_bricks() )
    def get_compatible_portal_blocks(self, app_name):
        method_name = 'home_display' if app_name == 'creme_core' else 'portal_display'

        for brick_cls in self._brick_classes.itervalues():
            brick = brick_cls()

            if brick.configurable and hasattr(brick, method_name) \
                    and (not brick.target_apps or app_name in brick.target_apps):
                yield brick

        for ibi in InstanceBlockConfigItem.objects.all():
            block = self.get_brick_4_instance(ibi)

            if hasattr(block, method_name) and \
                    (not block.target_apps or app_name in block.target_apps):
                yield block

    def is_model_invalid(self, model):
        "See register_invalid_model"
        return model in self._invalid_models


brick_registry = _BrickRegistry()