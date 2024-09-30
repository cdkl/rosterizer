from django import forms
from .models import Session

class SessionForm(forms.ModelForm):
	class Meta:
		model = Session
		fields = ['year', 'session_number']
        
class PlayerImportForm(forms.Form):
    player_file = forms.FileField(label='Select an HTML file from CCM, or a CSV export if you have corrections')

class RosterImportForm(forms.Form):
    roster_file = forms.FileField(label='Select a roster file')