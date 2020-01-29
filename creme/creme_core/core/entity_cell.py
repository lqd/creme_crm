# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2013-2020  Hybird
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
from typing import Type, Iterable, Optional, Dict, List, Tuple  # Callable

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Model, Field, FieldDoesNotExist, BooleanField, DateField
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from ..models import CremeEntity, RelationType, CustomField
from ..models import fields as core_fields
from ..utils.collections import ClassKeyedMap
from ..utils.db import populate_related
from ..utils.meta import FieldInfo
from ..utils.unicode_collation import collator

from .function_field import (
    FunctionField,
    FunctionFieldDecimal,
    FunctionFieldResultsList,
    function_field_registry,
)

# TODO: rename EntityCell to [Model]Cell ?
#       rename 'entity' argument to 'instance'.

logger = logging.getLogger(__name__)
MULTILINE_FIELDS = (
    models.TextField,
    core_fields.UnsafeHTMLField,
    models.ManyToManyField,
)
FIELDS_DATA_TYPES = ClassKeyedMap([
    (DateField,                   'date'),
    (models.TimeField,            'time'),
    (models.DateTimeField,        'datetime'),

    (models.IntegerField,         'integer'),

    (models.TextField,            'text'),
    (models.EmailField,           'email'),

    (core_fields.PhoneField,      'phone'),
    (core_fields.DurationField,   'duration'),
    (core_fields.DatePeriod,      'period'),
    (core_fields.ColorField,      'color'),
    (core_fields.UnsafeHTMLField, 'html'),
    (core_fields.MoneyField,      'html'),
])


class EntityCell:
    """Represents a value accessor ; it's a kind of super field. It can
    retrieve a value store in entities (of the same type).
    This values can be (see child classes) :
     - regular fields (in the django model way).
     - custom field (see models.CustomField).
     - function fields (see core.FunctionField).
     - other entities linked by a Relation (of a given RelationType).
     - ...
    """
    # type_id = None
    type_id: str  # Used for register ; overload in child classes (string type)
    value: str
    is_hidden: bool

    _listview_css_class = None
    _header_listview_css_class = None

    def __init__(self, model: Type[Model], value: str = '', title='Title', is_hidden: bool = False):
        self._model = model
        self.value = value
        self.title = title
        self.is_hidden = is_hidden

    def __repr__(self):
        return f"<EntityCell(type={self.type_id}, value='{self.value}')>"

    def __str__(self):
        return self.title

    def _get_field_class(self) -> Type[Field]:
        return Field

    def _get_listview_css_class(self, attr_name: str):
        from ..gui.field_printers import field_printers_registry

        listview_css_class = getattr(self, attr_name)

        if listview_css_class is None:
            registry_getter = getattr(field_printers_registry, f'get{attr_name}_for_field')
            listview_css_class = registry_getter(self._get_field_class())
            setattr(self, attr_name, listview_css_class)

        return listview_css_class

    @classmethod
    def build(cls, model: Type[Model], name: str):
        raise NotImplementedError

    @property
    def data_type(self) -> Optional[str]:
        return FIELDS_DATA_TYPES[self._get_field_class()]

    @property
    def model(self) -> Type[Model]:
        return self._model

    @property
    def key(self) -> str:
        "Return an ID that should be unique in a EntityCell set."
        return f'{self.type_id}-{self.value}'

    @property
    def listview_css_class(self) -> str:
        return self._get_listview_css_class('_listview_css_class')

    @property
    def header_listview_css_class(self) -> str:
        return self._get_listview_css_class('_header_listview_css_class')

    @property
    def is_multiline(self) -> bool:
        return issubclass(self._get_field_class(), MULTILINE_FIELDS)

    @staticmethod
    def populate_entities(cells, entities, user):
        pass

    # TODO: factorise render_* => like FunctionField, result that can be html, csv...
    def render_html(self, entity: CremeEntity, user):
        raise NotImplementedError

    def render_csv(self, entity: CremeEntity, user):
        raise NotImplementedError

    def to_dict(self):
        return {'type': self.type_id, 'value': self.value}


class EntityCellsRegistry:
    __slots__ = ('_cell_classes', )

    class RegistrationError(Exception):
        pass

    def __init__(self):
        self._cell_classes: Dict[str, Type[EntityCell]] = {}

    def __call__(self, cls):
        if self._cell_classes.setdefault(cls.type_id, cls) is not cls:
            raise self.RegistrationError(f'Duplicated Cell id: {cls.id}')

        return cls

    def __getitem__(self, type_id: str):
        return self._cell_classes[type_id]

    def build_cells_from_dicts(self,
                               model: Type[Model],
                               dicts: Iterable[Dict]) -> Tuple[List[EntityCell], bool]:
        """Build some EntityCells instance from an iterable of dictionaries.

        @param model: Class inheriting <django.db.model.Model> related to the cells.
        @param dicts: Iterable of dictionaries ; see 'EntityCell.to_dict()'.
        @return: tuple(list_of_cells, errors) ; 'errors' is a boolean.
        """
        cells = []
        errors = False

        try:
            for dict_cell in dicts:
                try:
                    cell = self._cell_classes[dict_cell['type']].build(model, dict_cell['value'])

                    if cell is not None:
                        cells.append(cell)
                    else:
                        errors = True
                except Exception as e:
                    logger.warning('EntityCellsRegistry: %s, %s', e.__class__, e)
                    errors = True
        except Exception as e:
            logger.warning('EntityCellsRegistry: %s, %s', e.__class__, e)
            errors = True

        return cells, errors


CELLS_MAP = EntityCellsRegistry()


# @CELLS_MAP TODO
class EntityCellActions(EntityCell):
    type_id = 'actions'

    def __init__(self, model, actions_registry):
        """Constructor.

        @param model: see <EntityCell.model>.
        @param actions_registry: Instance of 'creme.creme_core.gui.actions.ActionsRegistry'.
               Used to get the actions related to the model.
        """
        super().__init__(model=model, value='entity_actions', title=_('Actions'))
        self.registry = actions_registry

    def _sort_actions(self, actions):
        collator_key = collator.sort_key
        actions.sort(key=lambda a: (not a.is_default, collator_key(a.label)))

        return actions

    def bulk_actions(self, user):
        """Get a sorted list of the visible <gui.actions.BulkAction> instances
        corresponding to the registered bulk actions (see 'registry' attribute).

        @param user: User who displays this page (used to compute credentials).
               Instance of 'django.contrib.auth.get_auth_model()'.
        @return: A list of instances of 'gui.actions.BulkActions'.
        """
        # TODO: filter by is_visible in actions_registry.bulk_actions() ??
        return self._sort_actions([
            action for action in self.registry.bulk_actions(user=user,
                                                            model=self.model,
                                                           )
                if action.is_visible
        ])

    def instance_actions(self, instance: Model, user):
        """Get a sorted list of the visible <gui.actions.UIAction> instances
        corresponding to the registered instance actions (see 'registry' attribute).

        @param instance: Should be an instance of 'self.model'.
        @param user: User who displays this page (used to compute credentials).
               Instance of 'django.contrib.auth.get_auth_model()'.
        @return: A list of instances of 'gui.actions.UIActions'.
        """
        # TODO: filter by is_visible in actions_registry.instance_actions() ??
        return self._sort_actions([
            action for action in self.registry.instance_actions(user=user,
                                                                instance=instance,
                                                               )
                if action.is_visible
        ])

    def render_html(self, entity: CremeEntity, user) -> str:
        return ''

    def render_csv(self, entity: CremeEntity, user) -> str:
        return ''


@CELLS_MAP
class EntityCellRegularField(EntityCell):
    type_id = 'regular_field'

    def __init__(self, model, name, field_info: FieldInfo, is_hidden=False):
        "Use build() instead of using this constructor directly."
        self._field_info = field_info
        self._printer_html = self._printer_csv = None

        super().__init__(model=model,
                         value=name,
                         title=field_info.verbose_name,
                         is_hidden=is_hidden,
                        )

    @classmethod
    def build(cls, model: Type[Model], name: str, is_hidden: bool = False):
        """ Helper function to build EntityCellRegularField instances.

        @param model: Class inheriting django.db.models.Model.
        @param name: String representing a 'chain' of fields; eg: 'book__author__name'.
        @param is_hidden: Boolean. See EntityCell.is_hidden.
        @return: An instance of EntityCellRegularField, or None (if an error occurred).
        """
        try:
            field_info = FieldInfo(model, name)
        except FieldDoesNotExist as e:
            logger.warning('EntityCellRegularField(): problem with field "%s" ("%s")', name, e)
            return None

        return cls(model, name, field_info, is_hidden)

    @property
    def field_info(self) -> FieldInfo:
        """ Getter for attribute 'field_info'.

        @return: An instance of creme_core.utils.meta.FieldInfo.
        """
        return self._field_info

    @property
    def is_multiline(self):
        return any(isinstance(f, MULTILINE_FIELDS) for f in self._field_info)

    def _get_field_class(self):
        return self._field_info[-1].__class__

    @staticmethod
    def populate_entities(cells, entities, user):
        populate_related(entities, [cell.value for cell in cells])

    def render_html(self, entity, user):
        printer = self._printer_html

        if printer is None:
            # TODO: pass the 'field_printers_registry' in a context dict when building our instance
            #       (see EntityCellFunctionField too)
            from ..gui.field_printers import field_printers_registry

            self._printer_html = printer = \
                 field_printers_registry.build_field_printer(entity.__class__, self.value, output='html')

        return printer(entity, user)

    def render_csv(self, entity, user):
        printer = self._printer_csv

        if printer is None:
            from ..gui.field_printers import field_printers_registry

            self._printer_csv = printer = \
                field_printers_registry.build_field_printer(entity.__class__, self.value, output='csv')

        return printer(entity, user)


@CELLS_MAP
class EntityCellCustomField(EntityCell):
    type_id = 'custom_field'

    _CF_CSS = {
        CustomField.DATETIME:   models.DateTimeField,
        CustomField.INT:        models.PositiveIntegerField,
        CustomField.FLOAT:      models.DecimalField,
        CustomField.BOOL:       BooleanField,
        CustomField.ENUM:       models.ForeignKey,
        CustomField.MULTI_ENUM: models.ManyToManyField,
    }

    def __init__(self, customfield: CustomField):
        self._customfield = customfield

        super().__init__(model=customfield.content_type.model_class(),
                         value=str(customfield.id),
                         title=customfield.name,
                         is_hidden=False,
                        )

    @classmethod
    def build(cls, model: Type[Model], customfield_id: str):
        ct = ContentType.objects.get_for_model(model)

        try:
            cfield = CustomField.objects.get(content_type=ct, id=customfield_id)
        except CustomField.DoesNotExist:
            logger.warning(
                'EntityCellCustomField: custom field "%s" does not exist',
                customfield_id,
            )
            return None

        return cls(cfield)

    @property
    def custom_field(self) -> CustomField:
        return self._customfield

    def _get_field_class(self):
        return self._CF_CSS.get(self._customfield.field_type, Field)

    @staticmethod
    def populate_entities(cells, entities, user):
        CremeEntity.populate_custom_values(
            entities,
            [cell.custom_field for cell in cells],
        )  # NB: not itervalues()

    def render_html(self, entity, user):
        from django.utils.html import escape
        return escape(self.render_csv(entity, user))

    def render_csv(self, entity, user):
        value = entity.get_custom_value(self.custom_field)
        return value if value is not None else ''


@CELLS_MAP
class EntityCellFunctionField(EntityCell):
    type_id = 'function_field'

    _FUNFIELD_CSS = {  # TODO: ClassKeyedMap ?
        FunctionFieldDecimal: models.DecimalField,
    }

    def __init__(self, model, func_field: FunctionField):
        self._functionfield = func_field

        super().__init__(model=model,
                         value=func_field.name,
                         title=str(func_field.verbose_name),
                         is_hidden=func_field.is_hidden,
                        )

    @classmethod
    def build(cls, model: Type[Model], func_field_name: str):
        # TODO: pass the 'function_field_registry' in a context
        func_field = function_field_registry.get(model, func_field_name)

        if func_field is None:
            logger.warning('EntityCellFunctionField: function field "%s" does not exist', func_field_name)
            return None

        return cls(model=model, func_field=func_field)

    @property
    def function_field(self) -> FunctionField:
        return self._functionfield

    def _get_field_class(self):
        return self._FUNFIELD_CSS.get(self._functionfield.result_type, Field)

    @property
    def is_multiline(self):
        return issubclass(self._functionfield.result_type, FunctionFieldResultsList)

    @staticmethod
    def populate_entities(cells, entities, user):
        for cell in cells:
            cell.function_field.populate_entities(entities, user)

    def render_html(self, entity, user):
        return self.function_field(entity, user).for_html()

    def render_csv(self, entity, user):
        return self.function_field(entity, user).for_csv()


@CELLS_MAP
class EntityCellRelation(EntityCell):
    type_id = 'relation'

    def __init__(self, model: Type[Model], rtype: RelationType, is_hidden: bool = False):
        self._rtype = rtype
        super().__init__(model=model,
                         value=str(rtype.id),
                         title=rtype.predicate,
                         is_hidden=is_hidden,
                        )

    @classmethod
    def build(cls, model: Type[Model], rtype_id: str, is_hidden: bool = False):
        try:
            rtype = RelationType.objects.get(pk=rtype_id)
        except RelationType.DoesNotExist:
            logger.warning('EntityCellRelation: relation type "%s" does not exist', rtype_id)
            return None

        return cls(model=model, rtype=rtype, is_hidden=is_hidden)

    @property
    def is_multiline(self):
        return True

    @property
    def relation_type(self) -> RelationType:
        return self._rtype

    @staticmethod
    def populate_entities(cells, entities, user):
        CremeEntity.populate_relations(entities, [cell.relation_type.id for cell in cells])

    def render_html(self, entity, user):
        from ..templatetags.creme_widgets import widget_entity_hyperlink

        related_entities = entity.get_related_entities(self.value, True)

        if not related_entities:
            return ''

        if len(related_entities) == 1:
            return widget_entity_hyperlink(related_entities[0], user)

        return format_html('<ul>{}</ul>',
                           format_html_join(
                               '', '<li>{}</li>',
                               ([widget_entity_hyperlink(e, user)] for e in related_entities)
                           )
                          )

    def render_csv(self, entity, user):
        has_perm = user.has_perm_to_view
        return '/'.join(str(o)
                            for o in entity.get_related_entities(self.value, True)
                                if has_perm(o)
                       )


# @CELLS_MAP TODO ??
class EntityCellVolatile(EntityCell):
    type_id = 'volatile'

    def __init__(self,
                 model: Type[Model],
                 value, title,
                 render_func,  # TODO: Callable[[CremeEntity], str] VS abstract render_html() (see "events" app)
                 is_hidden: bool = False):
        self._render_func = render_func
        super().__init__(model=model,
                         value=value,
                         title=title,
                         is_hidden=is_hidden,
                        )

    def render_html(self, entity, user):
        return self._render_func(entity)  # TODO: pass user
