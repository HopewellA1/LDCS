from django import forms
from django.forms import inlineformset_factory

from .models import FollowUpQuestion, FollowUpTest

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


# ---------------------------------------------------------------------------
# Follow-up tests: an officer builds a small practice test for a student,
# targeting a domain they struggled with. A ModelForm for the test itself,
# plus an inline formset for its questions (the "add another question" pattern).
# ---------------------------------------------------------------------------

class _StyledMixin:
    """Give every non-checkbox widget the site's input class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            existing = widget.attrs.get("class", "")
            widget.attrs["class"] = f"{existing} form-input".strip()


class FollowUpTestForm(_StyledMixin, forms.ModelForm):
    class Meta:
        model = FollowUpTest
        fields = ["title", "domain", "note", "is_active"]
        widgets = {
            "note": forms.Textarea(attrs={"rows": 2,
                                          "placeholder": "Optional note shown to the student"}),
        }


class FollowUpQuestionForm(_StyledMixin, forms.ModelForm):
    class Meta:
        model = FollowUpQuestion
        fields = ["prompt", "option_a", "option_b", "option_c", "option_d", "correct_index"]

    def clean(self):
        cleaned = super().clean()
        # A completely empty extra row is fine - the formset just drops it.
        prompt = (cleaned.get("prompt") or "").strip()
        if not prompt:
            return cleaned
        options = [cleaned.get(f) for f in ("option_a", "option_b", "option_c", "option_d")]
        filled = [bool((o or "").strip()) for o in options]
        if sum(filled) < 2:
            self.add_error("option_b", "Give at least two options.")
        idx = cleaned.get("correct_index") or 0
        if idx >= len(options) or not filled[idx]:
            self.add_error("correct_index", "The option marked correct must be filled in.")
        return cleaned


# extra=3 blank rows to start; can add/remove; at least one real question required.
FollowUpQuestionFormSet = inlineformset_factory(
    FollowUpTest,
    FollowUpQuestion,
    form=FollowUpQuestionForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)