"""
Train the predicted-risk model and save it for the dashboard to use.

Usage:
    python manage.py train_risk_model
    python manage.py train_risk_model --samples 1000 --noise 0.08
    python manage.py train_risk_model --no-backfill

It trains a RandomForest on synthetic data (see screening/ml.py for why the
data is synthetic and what that means), prints how it performed, saves the
model to screening/ml_model.pkl, and - unless --no-backfill is given -
predicts a risk level for every existing completed screening so the
dashboard is populated straight away.
"""

from django.core.management.base import BaseCommand

from ... import ml
from ...models import ScreeningSession


class Command(BaseCommand):
    help = "Train the predicted-risk RandomForest model and save it to disk."

    def add_arguments(self, parser):
        parser.add_argument(
            "--samples", type=int, default=600,
            help="Number of synthetic training profiles to generate (default 600).",
        )
        parser.add_argument(
            "--noise", type=float, default=0.05,
            help="Fraction of training labels to flip, 0-1 (default 0.05).",
        )
        parser.add_argument(
            "--no-backfill", action="store_true",
            help="Skip scoring existing completed screenings after training.",
        )

    def handle(self, *args, **options):
        # scikit-learn is optional for the app but required to train. Fail with
        # a clear message rather than a raw ImportError traceback.
        try:
            import sklearn  # noqa: F401
        except ImportError:
            self.stderr.write(self.style.ERROR(
                "scikit-learn is not installed. Install it first:\n"
                "    pip install scikit-learn"
            ))
            return

        samples = options["samples"]
        noise = options["noise"]

        self.stdout.write(
            f"Training on {samples} synthetic profiles (label noise {noise:.0%})..."
        )
        model, metrics = ml.train(n=samples, noise=noise)
        ml.save_model(model)

        self._report(metrics)
        self.stdout.write(self.style.SUCCESS(f"\nModel saved to {ml.MODEL_PATH}"))

        if not options["no_backfill"]:
            self._backfill(model)

    def _report(self, metrics):
        """Print the training metrics in a readable block."""
        self.stdout.write("")
        self.stdout.write(
            f"  Train accuracy: {metrics['train_accuracy']:.1%}   "
            f"Test accuracy: {metrics['test_accuracy']:.1%}"
        )

        labels = metrics["labels"]
        self.stdout.write("\n  Confusion matrix (rows = actual, cols = predicted):")
        header = "           " + "".join(f"{lab:>9}" for lab in labels)
        self.stdout.write(header)
        for lab, row in zip(labels, metrics["confusion"]):
            cells = "".join(f"{val:>9}" for val in row)
            self.stdout.write(f"    {lab:>7}{cells}")

        self.stdout.write("\n  Feature importance (which signals the model relied on):")
        for name, value in metrics["importances"]:
            bar = "#" * round(value * 40)
            self.stdout.write(f"    {name:>12}  {value:5.3f}  {bar}")

    def _backfill(self, model):
        """Predict and store a risk level for every completed screening."""
        sessions = (
            ScreeningSession.objects
            .filter(completed_at__isnull=False)
            .prefetch_related("domain_results")
        )
        updated = 0
        for session in sessions:
            risk = ml.predict_risk(session, model=model)
            if risk and session.ml_risk != risk:
                session.ml_risk = risk
                session.save(update_fields=["ml_risk"])
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"Backfilled predicted risk on {updated} existing screening(s)."
        ))
