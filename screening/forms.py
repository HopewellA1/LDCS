from django import forms

REQUIRED = {"required": "Please tick this box to continue."}


class ConsentForm(forms.Form):
    understood = forms.BooleanField(
        label="I have read and understood the information above.",
        error_messages=REQUIRED,
    )
    voluntary = forms.BooleanField(
        label="I understand that taking part is voluntary and that I can withdraw my consent at any time.",
        error_messages=REQUIRED,
    )
    not_diagnosis = forms.BooleanField(
        label="I understand that the screening result is not a diagnosis.",
        error_messages=REQUIRED,
    )
    data_use = forms.BooleanField(
        label="I agree to LDCS collecting and analysing the information I provide for screening purposes.",
        error_messages=REQUIRED,
    )