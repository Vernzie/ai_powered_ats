from django.contrib import admin

from .models import Application, Criterion, Job, Requirement


class RequirementInline(admin.TabularInline):
	model = Requirement
	extra = 0
	fields = ('description', 'required')


class CriterionInline(admin.TabularInline):
	model = Criterion
	extra = 0
	fields = ('name',)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
	list_display = ('title', 'location', 'salary', 'deadline', 'posted_date')
	list_filter = ('location', 'deadline')
	search_fields = ('title', 'location', 'description')
	ordering = ('-posted_date',)
	inlines = (CriterionInline,)


@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
	list_display = ('description', 'criterion', 'required')
	list_filter = ('required', 'criterion__job')
	search_fields = ('description', 'criterion__name', 'criterion__job__title')
	list_select_related = ('criterion', 'criterion__job')


@admin.register(Criterion)
class CriterionAdmin(admin.ModelAdmin):
	list_display = ('name', 'job')
	list_filter = ('job',)
	search_fields = ('name', 'job__title')
	ordering = ('job', 'name')
	inlines = (RequirementInline,)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
	list_display = ('applicant_name', 'applicant_email', 'job', 'status', 'applied_date')
	list_filter = ('status', 'job', 'applied_date')
	search_fields = ('applicant_name', 'applicant_email', 'job__title')
	ordering = ('-applied_date',)
