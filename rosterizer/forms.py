from django import forms
from .models import Session

class SessionForm(forms.ModelForm):
	class Meta:
		model = Session
		fields = ['year', 'session_number']