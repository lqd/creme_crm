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

from functools import partial
from datetime import datetime, time
from logging import debug

from django.forms import IntegerField, BooleanField, ModelChoiceField, ModelMultipleChoiceField
from django.forms.util import ValidationError, ErrorList
from django.utils.translation import ugettext_lazy as _, ugettext
from django.db.models import Q
from django.contrib.auth.models import User

from creme_core.models import CremeEntity, Relation, RelationType
from creme_core.forms import CremeForm, CremeEntityForm
from creme_core.forms.fields import RelatedEntitiesField, CremeDateTimeField, CremeTimeField, MultiCremeEntityField, MultiGenericEntityField
from creme_core.forms.widgets import UnorderedMultipleChoiceWidget

from persons.models import Contact

from assistants.models.alert import Alert


from activities.models import Activity, Calendar, CalendarActivityLink
from activities.constants import *


def _clean_interval(cleaned_data):
    if cleaned_data.get('is_all_day'):
        cleaned_data['start_time'] = time(hour=0,  minute=0)
        cleaned_data['end_time']   = time(hour=23, minute=59)

    start_time = cleaned_data.get('start_time') or time()
    end_time   = cleaned_data.get('end_time') or time()

    cleaned_data['start'] = cleaned_data['start'].replace(hour=start_time.hour, minute=start_time.minute)

    if not cleaned_data.get('end'):
        cleaned_data['end'] = cleaned_data['start']

    cleaned_data['end'] = cleaned_data['end'].replace(hour=end_time.hour, minute=end_time.minute)

    if cleaned_data['start'] > cleaned_data['end']:
        raise ValidationError(ugettext(u"End time is before start time"))

def _check_activity_collisions(activity_start, activity_end, participants, exclude_activity_id=None):
    collision_test = ~(Q(end__lte=activity_start) | Q(start__gte=activity_end))
    collisions     = []

    for participant in participants:
        # find activities of participant
        activity_req = Relation.objects.filter(subject_entity=participant.id, type=REL_SUB_PART_2_ACTIVITY)

        # exclude current activity if asked
        if exclude_activity_id is not None:
            activity_req = activity_req.exclude(object_entity=exclude_activity_id)

        # get id of activities of participant
        activity_ids = activity_req.values_list("object_entity__id", flat=True)

        # do collision request
        #TODO: can be done with less queries ?
        #  eg:  Activity.objects.filter(relations__object_entity=participant.id, relations__object_entity__type=REL_OBJ_PART_2_ACTIVITY).filter(collision_test)
        #activity_collisions = Activity.objects.exclude(busy=False).filter(pk__in=activity_ids).filter(collision_test)[:1]
        activity_collisions = Activity.objects.filter(pk__in=activity_ids).filter(collision_test)[:1]

        if activity_collisions:
            collision = activity_collisions[0]
            collision_start = max(activity_start.time(), collision.start.time())
            collision_end   = min(activity_end.time(),   collision.end.time())

            collisions.append(ugettext(u"%(participant)s already participates to the activity «%(activity)s» between %(start)s and %(end)s.") % {
                        'participant': participant,
                        'activity':    collision,
                        'start':       collision_start,
                        'end':         collision_end,
                    })

    if collisions:
        raise ValidationError(collisions)

#TODO: factorise with ActivityCreateForm ??
class ParticipantCreateForm(CremeForm):
    participants = MultiCremeEntityField(label=_(u'Participants'), model=Contact)

    def __init__(self, activity, *args, **kwargs):
        super(ParticipantCreateForm, self).__init__(*args, **kwargs)
        self.activity = activity
        self.participants = []

        existing = Contact.objects.filter(relations__type=REL_SUB_PART_2_ACTIVITY, relations__object_entity=activity.id)
        self.fields['participants'].q_filter = {'~pk__in': [c.id for c in existing]}

    def clean(self):
        cleaned_data = self.cleaned_data

        if not self._errors:
            activity = self.activity

            self.participants += cleaned_data['participants']

            if activity.busy:
                _check_activity_collisions(activity.start, activity.end, self.participants)

        return cleaned_data

    def save(self):
        activity = self.activity
        create_link = CalendarActivityLink.objects.get_or_create
        create_relation = partial(Relation.objects.create, object_entity=activity,
                                  type_id=REL_SUB_PART_2_ACTIVITY, user=activity.user
                                 )

        for participant in self.participants:
            if participant.is_user:
                create_link(calendar=Calendar.get_user_default_calendar(participant.is_user), activity=activity)

            create_relation(subject_entity=participant)


class SubjectCreateForm(CremeForm):
    subjects = RelatedEntitiesField(relation_types=[REL_SUB_ACTIVITY_SUBJECT], label=_(u'Subjects'), required=False)
    #subjects = MultiGenericEntityField(label=_(u'Subjects')) #TODO: use when bug with innerpopup is fixed ; filter already linked

    def __init__(self, activity, *args, **kwargs):
        super(SubjectCreateForm, self).__init__(*args, **kwargs)
        self.activity = activity

    def save (self):
        activity = self.activity
        create_relation = partial(Relation.objects.create, object_entity=activity, user=activity.user)

        for relationtype_id, entity in self.cleaned_data['subjects']:
            create_relation(subject_entity=entity, type_id=relationtype_id)


class ActivityCreateForm(CremeEntityForm):
    class Meta(CremeEntityForm.Meta):
        model = Activity
        exclude = CremeEntityForm.Meta.exclude + ('end',)

    start      = CremeDateTimeField(label=_(u'Start'))
    start_time = CremeTimeField(label=_(u'Start time'), required=False)
    end_time   = CremeTimeField(label=_(u'End time'), required=False)


    my_participation    = BooleanField(required=False, label=_(u"Do I participate to this meeting ?"))
    my_calendar         = ModelChoiceField(queryset=Calendar.objects.none(), required=False, label=_(u"On which of my calendar this activity will appears?"), empty_label=None)
    participating_users = ModelMultipleChoiceField(label=_(u'Other participating users'), queryset=User.objects.all(),
                                                   required=False, widget=UnorderedMultipleChoiceWidget
                                                  )
    other_participants  = MultiCremeEntityField(label=_(u'Other participants'), model=Contact, required=False)
    subjects            = MultiGenericEntityField(label=_(u'Subjects'), required=False)
    linked_entities     = MultiGenericEntityField(label=_(u'Entities linked to this activity'), required=False)


    generate_alert   = BooleanField(label=_(u"Do you want to generate an alert or a reminder ?"), required=False)
    alert_day        = CremeDateTimeField(label=_(u"Alert day"), required=False)
    alert_start_time = CremeTimeField(label=_(u"Alert time"), required=False)

    blocks = CremeEntityForm.blocks.new(
                ('datetime',       _(u'When'),                   ['start', 'start_time', 'end_time', 'is_all_day']),
                ('participants',   _(u'Participants'),           ['my_participation', 'my_calendar', 'participating_users', 'other_participants', 'subjects', 'linked_entities']),
                ('alert_datetime', _(u'Generate an alert or a reminder'), ['generate_alert', 'alert_day', 'alert_start_time']),
            )

    def __init__(self, current_user, *args, **kwargs):
        super(ActivityCreateForm, self).__init__(*args, **kwargs)
        self.current_user = current_user
        self.participants = []

        fields = self.fields

        fields['start_time'].initial = time(9, 0)
        fields['end_time'].initial   = time(18, 0)

        my_default_calendar = Calendar.get_user_default_calendar(current_user) #TODO: variable used once...
        fields['my_calendar'].queryset = Calendar.objects.filter(user=current_user)
        fields['my_calendar'].initial  = my_default_calendar

        #TODO: refactor this with a smart widget that manages dependencies
        data = kwargs.get('data') or {}
        if not data.get('my_participation', False):
            fields['my_calendar'].widget.attrs['disabled'] = 'disabled'
        fields['my_participation'].widget.attrs['onclick'] = "if($(this).is(':checked')){$('#id_my_calendar').removeAttr('disabled');}else{$('#id_my_calendar').attr('disabled', 'disabled');}"

        fields['participating_users'].queryset = User.objects.exclude(pk=current_user.id)
        fields['other_participants'].q_filter = {'is_user__isnull': True}

    def clean(self):
        cleaned_data = self.cleaned_data

        if self._errors:
            return cleaned_data

        _clean_interval(cleaned_data)

        users = list(cleaned_data['participating_users'])

        if cleaned_data.get('my_participation'):
            if not cleaned_data.get('my_calendar'):
                self.errors['my_calendar'] = ErrorList([_(u"If you participe, you have to choose one of your calendars.")])
            else:
                users.append(self.current_user)

        self.participants.extend(Contact.objects.filter(is_user__in=users))
        self.participants += cleaned_data['other_participants']

        if cleaned_data['busy']:
            _check_activity_collisions(cleaned_data['start'], cleaned_data['end'], self.participants)

        return cleaned_data

    def save(self):
        instance     = self.instance
        cleaned_data = self.cleaned_data

        instance.end = cleaned_data['end']
        super(ActivityCreateForm, self).save()

        self._generate_alert()

        create_link = CalendarActivityLink.objects.get_or_create

        if cleaned_data['my_participation']:
            create_link(calendar=cleaned_data['my_calendar'], activity=instance)

        for part_user in cleaned_data['participating_users']:
            #TODO: regroup queries ??
            create_link(calendar=Calendar.get_user_default_calendar(part_user), activity=instance)

        create_relation = partial(Relation.objects.create, object_entity=instance, user=instance.user)

        for participant in self.participants:
            create_relation(subject_entity=participant, type_id=REL_SUB_PART_2_ACTIVITY)

        for subject in cleaned_data['subjects']:
            create_relation(subject_entity=subject, type_id=REL_SUB_ACTIVITY_SUBJECT)

        for linked in cleaned_data['linked_entities']:
            create_relation(subject_entity=linked, type_id=REL_SUB_LINKED_2_ACTIVITY)

        return instance

    def _generate_alert(self):
        cleaned_data = self.cleaned_data

        if cleaned_data['generate_alert']:
            activity = self.instance

            alert_start_time = cleaned_data.get('alert_start_time') or time()
            alert_day        = cleaned_data.get('alert_day') or activity.start

            Alert.objects.create(for_user=activity.user,
                                 trigger_date=alert_day.replace(hour=alert_start_time.hour, minute=alert_start_time.minute),
                                 creme_entity=activity,
                                 title=ugettext(u"Alert of activity"),
                                 description=ugettext(u'Alert related to %s') % activity,
                                )


class RelatedActivityCreateForm(ActivityCreateForm):
    def __init__(self, entity_for_relation, relation_type, *args, **kwargs):
        super(RelatedActivityCreateForm, self).__init__(*args, **kwargs)
        fields = self.fields
        rtype_id = relation_type.id

        if rtype_id == REL_SUB_PART_2_ACTIVITY:
            assert isinstance(entity_for_relation, Contact)

            if entity_for_relation.is_user:
                self.fields['participating_users'].initial = [entity_for_relation.is_user]
            else:
                self.fields['other_participants'].initial = entity_for_relation.id
        elif rtype_id == REL_SUB_ACTIVITY_SUBJECT:
            self.fields['subjects'].initial = [entity_for_relation.id]
        else:
            assert rtype_id == REL_SUB_LINKED_2_ACTIVITY
            self.fields['linked_entities'].initial = [entity_for_relation.id]


#TODO: factorise ?? (ex: CreateForm inherits from EditForm....)
class ActivityEditForm(CremeEntityForm):
    start      = CremeDateTimeField(label=_(u'Start'))
    start_time = CremeTimeField(label=_(u'Start time'), required=False)
    end_time   = CremeTimeField(label=_(u'End time'), required=False)

    class Meta(CremeEntityForm.Meta):
        model = Activity
        exclude = CremeEntityForm.Meta.exclude + ('end', 'type')

    def __init__(self, *args, **kwargs):
        super(ActivityEditForm, self).__init__(*args, **kwargs)

        fields = self.fields
        instance = self.instance

        fields['start_time'].initial = instance.start.time()
        fields['end_time'].initial   = instance.end.time()

    def clean(self):
        cleaned_data = self.cleaned_data

        if self._errors:
            return cleaned_data

        instance = self.instance

        _clean_interval(cleaned_data)

        # check if activity period change cause collisions
        if cleaned_data['busy']:
            _check_activity_collisions(cleaned_data['start'], cleaned_data['end'],
                                       instance.get_related_entities(REL_OBJ_PART_2_ACTIVITY),
                                       instance.id
                                      )

        return cleaned_data

    def save(self):
        self.instance.end = self.cleaned_data['end']
        return super(ActivityEditForm, self).save()
