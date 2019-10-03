# -*- coding: utf-8 -*-

################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2019  Hybird
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

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _, gettext, pgettext

from creme.creme_core.apps import creme_app_configs, extended_app_configs, CremeAppConfig
from creme.creme_core.auth.entity_credentials import EntityCredentials
from creme.creme_core.forms import (
    CremeForm, CremeModelForm, FieldBlockManager,
    MultiEntityCTypeChoiceField,
    entity_filter as ef_forms,
)
from creme.creme_core.forms.widgets import Label, DynamicSelect, CremeRadioSelect
from creme.creme_core.models import CremeEntity, CremeUser, UserRole, SetCredentials, EntityFilter  # Mutex
from creme.creme_core.registry import creme_registry
from creme.creme_core.utils import update_model_instance
from creme.creme_core.utils.id_generator import generate_string_id_and_save
from creme.creme_core.utils.unicode_collation import collator


def filtered_entity_ctypes(app_labels):  # TODO: move to creme_core.utils ?? (improve iter_entity_models() ?)
    ext_app_labels = {app_config.label for app_config in extended_app_configs(app_labels)}
    get_ct = ContentType.objects.get_for_model

    for model in creme_registry.iter_entity_models():
        if model._meta.app_label in ext_app_labels:
            yield get_ct(model)


# def EmptyMultipleChoiceField(required=False, *args, **kwargs):
#     return MultipleChoiceField(required=required, choices=(), *args, **kwargs)

# class EditCredentialsForm(CremeModelForm):
#     can_view   = BooleanField(label=_('Can view'),   required=False)
#     can_change = BooleanField(label=_('Can change'), required=False)
#     can_delete = BooleanField(label=_('Can delete'), required=False)
#     can_link   = BooleanField(label=_('Can link'),   required=False,
#                               help_text=_('You must have the permission to link on 2 entities'
#                                           ' to create a relationship between them.'
#                                          ),
#                              )
#     can_unlink = BooleanField(label=_('Can unlink'), required=False,
#                               help_text=_('You must have the permission to unlink on 2 entities'
#                                           ' to delete a relationship between them.'
#                                          ),
#                              )
#     set_type   = ChoiceField(label=_('Type of entities set'),
#                              choices=SetCredentials.ESETS_MAP.items(),
#                              widget=CremeRadioSelect,
#                             )
#     ctype      = EntityCTypeChoiceField(label=_('Apply to a specific type'),
#                                         widget=DynamicSelect(attrs={'autocomplete': True}),
#                                         required=False,
#                                         empty_label=pgettext('content_type', 'None'),
#                                        )
#
#     class Meta:
#         model = SetCredentials
#         exclude = ('role', 'value')  # fields ??
#
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         fields = self.fields
#         fields['ctype'].ctypes = filtered_entity_ctypes(self._get_allowed_apps())
#
#         value = self.instance.value or 0
#         fields['can_view'].initial   = bool(value & EntityCredentials.VIEW)
#         fields['can_change'].initial = bool(value & EntityCredentials.CHANGE)
#         fields['can_delete'].initial = bool(value & EntityCredentials.DELETE)
#         fields['can_link'].initial   = bool(value & EntityCredentials.LINK)
#         fields['can_unlink'].initial = bool(value & EntityCredentials.UNLINK)
#
#     def _get_allowed_apps(self):
#         return self.instance.role.allowed_apps
#
#     def save(self, *args, **kwargs):
#         get_data = self.cleaned_data.get
#
#         self.instance.set_value(get_data('can_view'), get_data('can_change'), get_data('can_delete'),
#                                 get_data('can_link'), get_data('can_unlink')
#                                )
#
#         return super().save(*args, **kwargs)
class CredentialsGeneralStep(CremeModelForm):
    can_view   = forms.BooleanField(label=_('View'),   required=False)
    can_change = forms.BooleanField(label=_('Change'), required=False)
    can_delete = forms.BooleanField(label=_('Delete'), required=False)

    can_link = forms.BooleanField(
        label=_('Link'), required=False,
        help_text=_("You must have the permission to link on 2 entities "
                    "to create a relationship between them. "
                    "Beware: if you use «Filtered entities», you won't "
                    "be able to add relationships in the creation forms "
                    "(you'll have to add them later).",
                   ),
    )
    can_unlink = forms.BooleanField(
        label=_('Unlink'), required=False,
        help_text=_('You must have the permission to unlink on '
                    '2 entities to delete a relationship between them.'
                   ),
    )

    blocks = FieldBlockManager(
        ('general', _('General information'), '*'),
        ('actions', _('Actions'), ['can_view', 'can_change', 'can_delete', 'can_link', 'can_unlink']),
    )

    class Meta:
        model = SetCredentials
        # exclude = ('role', 'value')
        exclude = ('value', )  # fields ??
        widgets = {
            'set_type':  CremeRadioSelect,
            'ctype':     DynamicSelect(attrs={'autocomplete': True}),  # TODO: always this widget for CTypeForeignKey ??
            'forbidden': CremeRadioSelect,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fields = self.fields

        ctype_f = fields['ctype']
        ctype_f.empty_label = pgettext('content_type', 'None')
        ctype_f.ctypes = filtered_entity_ctypes(self._get_allowed_apps())

        # TODO: SetCredentials.value default to 0
        value = self.instance.value or 0
        fields['can_view'].initial   = bool(value & EntityCredentials.VIEW)
        fields['can_change'].initial = bool(value & EntityCredentials.CHANGE)
        fields['can_delete'].initial = bool(value & EntityCredentials.DELETE)
        fields['can_link'].initial   = bool(value & EntityCredentials.LINK)
        fields['can_unlink'].initial = bool(value & EntityCredentials.UNLINK)

    def _get_allowed_apps(self):
        return self.instance.role.allowed_apps

    def save(self, *args, **kwargs):
        get_data = self.cleaned_data.get
        self.instance.set_value(
            can_view=get_data('can_view'),
            can_change=get_data('can_change'),
            can_delete=get_data('can_delete'),
            can_link=get_data('can_link'),
            can_unlink=get_data('can_unlink'),
        )


class CredentialsFilterStep(CremeModelForm):
    name   = EntityFilter._meta.get_field('name').formfield(label=_('Name of the filter'))
    use_or = EntityFilter._meta.get_field('use_or').formfield(widget=CremeRadioSelect)

    fields_conditions = ef_forms.RegularFieldsConditionsField(
        label=_('On regular fields'), required=False,
        help_text=_('You can write several values, separated by commas.'),
    )
    customfields_conditions = ef_forms.CustomFieldsConditionsField(
        label=_('On custom fields'), required=False,
        help_text=_('Beware to performances.'),
    )
    relations_conditions = ef_forms.RelationsConditionsField(
        label=_('On relationships'), required=False,
        help_text=_('Do not select any entity if you want to match them all. '
                    'Beware to performances.'
                   ),
    )
    properties_conditions = ef_forms.PropertiesConditionsField(
        label=_('On properties'), required=False,
    )

    class Meta:
        model = SetCredentials
        fields = ()

    _CONDITIONS_FIELD_NAMES = (
        'fields_conditions',
        'customfields_conditions',
        'relations_conditions',
        'properties_conditions',
    )

    blocks = FieldBlockManager(
        ('general',    _('Filter'),     '*'),
        ('conditions', _('Conditions'), _CONDITIONS_FIELD_NAMES),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fields = self.fields

        if self.instance.set_type == SetCredentials.ESET_FILTER:
            instance = self.instance
            ctype = instance.ctype

            if ctype is None:
                del fields['customfields_conditions']
                ctype = ContentType.objects.get_for_model(CremeEntity)

            efilter = self.instance.efilter

            # NB: some explanations :
            #  - if the entity class related to the filter, we keep the current filter as initial.
            #  - if we pass from a Contact filter to an Organisation filter (for example),
            #     we do not use current filter as initial.
            #  - if we pass from a CremeEntity filter to an Organisation filter (for example),
            #    we keep the current filter as initial (the fields use are still valid).
            if efilter and issubclass(ctype.model_class(), efilter.entity_type.model_class()):
                fields['name'].initial = efilter.name
                fields['use_or'].initial = efilter.use_or

                f_init_args = (ctype, efilter.conditions.all(), efilter)
            else:
                f_init_args = (ctype,)

            for field_name in self._CONDITIONS_FIELD_NAMES:
                field = fields.get(field_name)

                if field:
                    field.initialize(*f_init_args)
        else:
            fields.clear()
            fields['no_filter_label'] = forms.CharField(
                label=_('Conditions'),
                required=False, widget=Label,
                initial=_('No filter, no condition.'),
            )

    def get_cleaned_conditions(self):
        cdata = self.cleaned_data
        conditions = []

        for fname in self._CONDITIONS_FIELD_NAMES:
            conditions.extend(cdata.get(fname, ()))

        return conditions

    def save(self, *args, **kwargs):
        instance = self.instance
        conditions = self.get_cleaned_conditions()
        efilter = instance.efilter

        if conditions:
            role = instance.role
            cdata = self.cleaned_data
            name = cdata['name']
            use_or = cdata['use_or']
            ctype = instance.ctype or \
                    ContentType.objects.get_for_model(CremeEntity)

            if efilter is None:
                efilter = EntityFilter(
                    name=name,
                    entity_type=ctype,
                    filter_type=EntityFilter.EF_SYSTEM,
                    use_or=use_or,
                )
                generate_string_id_and_save(
                    EntityFilter, [efilter],
                    'creme_core-credentials_{}-'.format(role.id),
                )
                instance.efilter = efilter
            else:
                update_model_instance(
                    efilter,
                    entity_type=ctype,
                    name=name,
                    use_or=use_or,
                )

            efilter.set_conditions(
                conditions,
                check_cycles=False,   # There cannot be a cycle without sub-filter.
                check_privacy=False,  # No sense here.
            )
            super().save(*args, **kwargs)
        elif efilter:
            instance.efilter = None
            super().save(*args, **kwargs)
            efilter.delete()
        else:
            super().save(*args, **kwargs)

        return instance


# class AddCredentialsForm(EditCredentialsForm):
#     def __init__(self, instance, *args, **kwargs):
#         self.role = instance
#         super().__init__(*args, **kwargs)
#         self.fields['set_type'].initial = SetCredentials.ESET_ALL
#
#     def _get_allowed_apps(self):
#         return self.role.allowed_apps
#
#     def save(self, *args, **kwargs):
#         self.instance.role = self.role
#         return super().save(*args, **kwargs)


class UserRoleDeleteForm(CremeForm):
    def __init__(self, user, instance, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.role_to_delete = instance
        self.using_users = users = CremeUser.objects.filter(role=instance)

        if users:
            self.fields['to_role'] = forms.ModelChoiceField(
                label=gettext('Choose a role to transfer to'),
                queryset=UserRole.objects.exclude(id=instance.id),
            )
        else:
            self.fields['info'] = forms.CharField(
                label=gettext('Information'), required=False, widget=Label,
                initial=gettext('This role is not used by any user,'
                                ' you can delete it safely.'
                               ),
            )

    def save(self, *args, **kwargs):
        to_role = self.cleaned_data.get('to_role')

        if to_role is not None:
            self.using_users.update(role=to_role)

        self.role_to_delete.delete()


# Wizard steps -----------------------------------------------------------------

class _UserRoleWizardFormStep(CremeModelForm):
    class Meta:
        model = UserRole
        fields = ()

    @staticmethod
    def app_choices(apps):
        sort_key = collator.sort_key

        return sorted(((app.label, str(app.verbose_name)) for app in apps),
                          key=lambda t: sort_key(t[1])
                     )

    # def partial_save(self):
    #     pass

    # def save(self, *args, **kwargs):
    #     self.partial_save()
    #     return super().save(*args, **kwargs)
    def save(self, commit=False, *args, **kwargs):
        return super().save(*args, **kwargs) if commit else self.instance


class UserRoleAppsStep(_UserRoleWizardFormStep):
    allowed_apps = forms.MultipleChoiceField(label=_('Allowed applications'), choices=())

    class Meta(_UserRoleWizardFormStep.Meta):
        fields = ('name', 'allowed_apps',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        CRED_REGULAR = CremeAppConfig.CRED_REGULAR
        allowed_apps_f = self.fields['allowed_apps']
        allowed_apps_f.choices = self.app_choices(
            app for app in creme_app_configs()
                if app.credentials & CRED_REGULAR
        )
        allowed_apps_f.initial = self.instance.allowed_apps

    def clean(self):
        cdata = super().clean()

        if not self._errors:
            self.instance.allowed_apps = self.cleaned_data['allowed_apps']

        return cdata

    # def partial_save(self):
    #     self.instance.allowed_apps = self.cleaned_data['allowed_apps']


class UserRoleAdminAppsStep(_UserRoleWizardFormStep):
    # admin_4_apps = EmptyMultipleChoiceField(label=_('Administrated applications'),
    #                                         help_text=_('These applications can be configured. '
    #                                                     'For example, the concerned users can create new choices '
    #                                                     'available in forms (eg: position for contacts).'
    #                                                    )
    #                                        )
    admin_4_apps = forms.MultipleChoiceField(
        required=False, choices=(),
        label=_('Administrated applications'),
        help_text=_('These applications can be configured. '
                    'For example, the concerned users can create new choices '
                    'available in forms (eg: position for contacts).'
                   ),
    )

    class Meta(_UserRoleWizardFormStep.Meta):
        fields = ('admin_4_apps',)

    # def __init__(self, allowed_app_names, *args, **kwargs):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        CRED_ADMIN = CremeAppConfig.CRED_ADMIN
        # labels = set(allowed_app_names)
        labels = self.instance.allowed_apps
        admin_4_apps_f = self.fields['admin_4_apps']
        admin_4_apps_f.choices = self.app_choices(app for app in creme_app_configs()
                                                        if app.label in labels and
                                                           app.credentials & CRED_ADMIN
                                                 )
        admin_4_apps_f.initial = self.instance.admin_4_apps

    def clean(self):
        cdata = super().clean()

        if not self._errors:
            self.instance.admin_4_apps = self.cleaned_data['admin_4_apps']

        return cdata

    # def partial_save(self):
    #     self.instance.admin_4_apps = self.cleaned_data['admin_4_apps']
    def save(self, commit=True, *args, **kwargs):
        return super().save(commit=commit, *args, **kwargs)


class UserRoleCreatableCTypesStep(_UserRoleWizardFormStep):
    creatable_ctypes = MultiEntityCTypeChoiceField(label=_('Creatable resources'), required=False)

    class Meta(_UserRoleWizardFormStep.Meta):
        fields = ('creatable_ctypes',)

    # def __init__(self, allowed_app_names, *args, **kwargs):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['creatable_ctypes'].ctypes = filtered_entity_ctypes(allowed_app_names)
        self.fields['creatable_ctypes'].ctypes = filtered_entity_ctypes(self.instance.allowed_apps)

    # def save(self, *args, **kwargs):
    #     # Optimisation: we only save the M2M
    #     self.instance.creatable_ctypes.set(self.cleaned_data['creatable_ctypes'])
    def save(self, commit=True, *args, **kwargs):
        instance = self.instance

        if commit:
            # Optimisation: we only save the M2M
            instance.creatable_ctypes.set(self.cleaned_data['creatable_ctypes'])

        return instance


class UserRoleExportableCTypesStep(_UserRoleWizardFormStep):
    exportable_ctypes = MultiEntityCTypeChoiceField(
        label=_('Exportable resources'), required=False,
        help_text=_('This types of entities can be downloaded as CSV/XLS '
                    'files (in the corresponding list-views).'
                   ),
    )

    class Meta(_UserRoleWizardFormStep.Meta):
        fields = ('exportable_ctypes',)

    # def __init__(self, allowed_app_names, *args, **kwargs):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields['exportable_ctypes'].ctypes = filtered_entity_ctypes(allowed_app_names)
        self.fields['exportable_ctypes'].ctypes = filtered_entity_ctypes(self.instance.allowed_apps)

    # def save(self, *args, **kwargs):
    #     # Optimisation: we only save the M2M
    #     self.instance.exportable_ctypes.set(self.cleaned_data['exportable_ctypes'])
    def save(self, commit=True, *args, **kwargs):
        instance = self.instance

        if commit:
            # Optimisation: we only save the M2M
            instance.exportable_ctypes.set(self.cleaned_data['exportable_ctypes'])

        return instance


# class UserRoleCredentialsStep(AddCredentialsForm):
#     blocks = FieldBlockManager(('general', _('First credentials'), '*'))
#
#     def __init__(self, allowed_app_names, *args, **kwargs):
#         self.allowed_app_names = allowed_app_names
#         super().__init__(*args, **kwargs)
#         fields = self.fields
#         fields['can_view'] = forms.CharField(
#             label=fields['can_view'].label,
#             required=False, widget=Label,
#             initial=_('Yes'),
#         )
#
#     def _get_allowed_apps(self):
#         return self.allowed_app_names
#
#     def clean_can_view(self):
#         return True
class UserRoleCredentialsGeneralStep(CredentialsGeneralStep):
    blocks = FieldBlockManager(
        ('general', _('First credentials: main information'), '*'),
        ('actions', _('First credentials: actions'),
         ['can_view', 'can_change', 'can_delete', 'can_link', 'can_unlink'],
        ),
    )

    def __init__(self, role, *args, **kwargs):
        self.role = role
        super().__init__(*args, **kwargs)
        fields = self.fields
        fields['can_view'] = forms.CharField(
            label=fields['can_view'].label,
            required=False, widget=Label,
            initial=_('Yes'),
        )

    def clean_can_view(self):
        return True

    def _get_allowed_apps(self):
        return self.role.allowed_apps

    def save(self, commit=False, *args, **kwargs):
        self.instance.role = self.role
        return super().save(commit=commit, *args, **kwargs)


class UserRoleCredentialsFilterStep(CredentialsFilterStep):
    blocks = FieldBlockManager(
        ('general',    _('First credentials: filter'),     '*'),
        ('conditions', _('First credentials: conditions'), CredentialsFilterStep._CONDITIONS_FIELD_NAMES),
    )

    def __init__(self, role, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role  # NB: not currently used, but facilitate extending
