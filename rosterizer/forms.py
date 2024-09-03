from django import forms
from .models import Session

class SessionForm(forms.ModelForm):
	class Meta:
		model = Session
		fields = ['year', 'session_number']
        
class PlayerImportForm(forms.Form):
    html_file = forms.FileField(label='Select an HTML file')
