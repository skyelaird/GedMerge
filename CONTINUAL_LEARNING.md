# Continual Learning System Documentation

## Overview

GedMerge now features a **comprehensive continual learning system** that automatically improves from user feedback. The system learns from ALL genealogical aspects: **names, places, events, and relationships**.

**Key Innovation**: Unlike traditional static ML models, GedMerge learns continuously from every user interaction, adapting to your specific genealogy database over time.

---

## Table of Contents

1. [What is Continual Learning?](#what-is-continual-learning)
2. [System Architecture](#system-architecture)
3. [Feedback Collection](#feedback-collection)
4. [Incremental Learning](#incremental-learning)
5. [Active Learning](#active-learning)
6. [Performance Monitoring](#performance-monitoring)
7. [Automated Retraining](#automated-retraining)
8. [API Reference](#api-reference)
9. [Usage Examples](#usage-examples)
10. [Best Practices](#best-practices)

---

## What is Continual Learning?

### Traditional ML (Batch Learning)
```
Train once → Deploy → Use static model → Eventually becomes stale
```

### Continual Learning (GedMerge)
```
Train → Deploy → Collect feedback → Update model → Improve accuracy → Repeat forever
```

### Benefits for Genealogy

✅ **Adapts to Your Data** - Learns patterns specific to your family tree
✅ **Improves from Corrections** - Every accepted/rejected suggestion teaches the system
✅ **Handles Data Drift** - Adapts as you add new records over time
✅ **No Manual Retraining** - Automatically updates when needed
✅ **Personalization** - Model becomes expert on YOUR genealogy data

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interactions                         │
│  (Confirm/Reject Duplicates, Correct Languages, Fix Quality) │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Feedback Database (SQLite)                      │
│  ┌─────────────┬──────────────┬──────────────┬────────────┐ │
│  │ Duplicates  │ Name Matches │ Languages    │ Quality    │ │
│  │ (All        │              │              │ Issues     │ │
│  │  Features)  │              │              │            │ │
│  └─────────────┴──────────────┴──────────────┴────────────┘ │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│  Performance     │    │  Active Learning │
│  Monitor         │    │  Module          │
│                  │    │                  │
│ • Track accuracy │    │ • Find uncertain │
│ • Detect drift   │    │   predictions    │
│ • Per-feature    │    │ • Prioritize     │
│   breakdown      │    │   review queue   │
└────────┬─────────┘    └──────────────────┘
         │
         ▼
┌──────────────────┐
│  Retraining      │
│  Scheduler       │
│                  │
│ • Check triggers │
│ • Auto-retrain   │
│ • Schedule runs  │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Incremental     │
│  Trainer         │
│                  │
│ • Update models  │
│ • Partial fit    │
│ • Version mgmt   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Updated Models  │
│  (Improved!)     │
└──────────────────┘
```

---

## Feedback Collection

### What Gets Captured

The system collects feedback on **ALL genealogical aspects**:

#### 1. Duplicate Detection Feedback
Captures ALL features used in matching:

**Names:**
- Name similarity score
- Surname match (yes/no)
- Given name match (yes/no)
- Phonetic match score

**Places:**
- Birth place match (yes/no)
- Death place match (yes/no)
- Overall place similarity (0-1)

**Dates:**
- Birth date match (yes/no)
- Death date match (yes/no)
- Date conflicts detected
- Age difference between records

**Relationships:**
- Number of shared parents
- Number of shared spouses
- Family structure match

**User Decision:**
- Predicted: duplicate or not
- User confirmed: yes or no
- Correction type: which aspect was wrong (name/date/place/relationship)

#### 2. Name Matching Feedback
- Two names being compared
- Predicted similarity (0-1)
- User confirmation (match or not)
- Language context for each name
- Surname vs given name breakdown

#### 3. Language Detection Feedback
- Name text
- Predicted language + confidence
- Correct language (user-provided)
- Place context (helps identify language)
- Other name variants for same person

#### 4. Quality Issue Feedback
- Person ID
- Predicted issues (list of 7 categories)
- Confidence scores per issue
- User-confirmed issues
- False positives (wrongly flagged)
- Missed issues (model didn't catch)

#### 5. Place Matching Feedback
- Two place names
- Predicted match + similarity
- User confirmation
- Geographic context (country, standardized names)

#### 6. Event Matching Feedback
- Event type (birth, death, marriage, etc.)
- Dates and places from both records
- Predicted match
- User confirmation
- Date precision indicators

### Database Schema

All feedback stored in SQLite database:
- `duplicate_feedback` - 23 columns capturing all features
- `name_match_feedback` - Name similarity corrections
- `language_feedback` - Language corrections
- `quality_feedback` - Quality issue corrections
- `place_feedback` - Place matching corrections
- `event_feedback` - Event matching corrections
- `performance_metrics` - Historical performance tracking

---

## Incremental Learning

### How It Works

Instead of full retraining from scratch, models update with new feedback:

1. **Collect Feedback** - User interactions stored in database
2. **Wait for Threshold** - Accumulate enough samples (50-100)
3. **Extract Features** - Convert feedback to training data
4. **Update Model** - Partial fit or warm-start training
5. **Version** - Save as new model version
6. **Deploy** - Automatically use updated model

### Update Strategies

#### Duplicate Detector (XGBoost/LightGBM)
- **Strategy**: Warm-start training
- **Minimum samples**: 50 feedback instances
- **Update frequency**: When threshold met or weekly
- **Learns from**: All 23 features (names, places, dates, relationships)

#### Language Detector (Multinomial NB)
- **Strategy**: Partial fit (true incremental learning)
- **Minimum samples**: 30 corrections
- **Update frequency**: When threshold met
- **Learns from**: Language corrections with place context

#### Name Matcher (Neural Network)
- **Strategy**: Continue training with new batches
- **Minimum samples**: 100 name pairs
- **Update frequency**: Monthly or on-demand
- **Learns from**: Confirmed/rejected name similarities

### Example Usage

```python
from gedmerge.ml.training.incremental_trainer import IncrementalTrainer

trainer = IncrementalTrainer()

# Update duplicate detector with new feedback
result = trainer.update_duplicate_detector(
    min_new_samples=50,
    strategy="warm_start"
)

print(f"Status: {result['status']}")
print(f"New version: {result['new_version']}")
print(f"Accuracy: {result['metrics']['accuracy']:.2%}")

# Update language detector
result = trainer.update_language_detector(min_new_samples=30)

# Update all models at once
results = trainer.update_all_models()
```

---

## Active Learning

### What is Active Learning?

Instead of randomly sampling for review, **active learning** identifies the **most valuable examples** to learn from.

### Uncertainty Sampling

The system identifies predictions where the model is uncertain:

**For Duplicate Detection:**
- Confidence near 50% (could go either way)
- Conflicting signals between features (e.g., name matches but dates don't)
- High variance in feature importance

**For Language Detection:**
- Low confidence predictions (< 70%)
- Names that could be multiple languages

**For Quality Classification:**
- Issues with borderline confidence (near 50%)
- Multiple uncertain issues per person

### Priority Scoring

Uncertain predictions are prioritized by **learning value**:

```python
priority_score = uncertainty * (1 + feature_variance)
```

Higher priority = review first!

### Usage

```python
from gedmerge.ml.active_learning import ActiveLearner

learner = ActiveLearner(
    duplicate_model=duplicate_model,
    language_model=language_model,
    quality_model=quality_model,
)

# Find uncertain duplicate predictions
uncertain = learner.find_uncertain_duplicates(
    person_pairs=all_pairs,
    uncertainty_threshold=0.15,  # Within 15% of 50%
    max_results=50
)

# Review top uncertain cases
for pred in uncertain[:10]:
    print(f"Confidence: {pred.confidence:.1%}")
    print(f"Uncertainty: {pred.uncertainty_score:.1%}")
    print(f"Reason: {pred.context['uncertainty_reason']}")
    print(f"Action: {pred.suggested_action}")
    print()

# Get combined review queue across all types
queue = learner.get_priority_review_queue(
    person_pairs=pairs,
    names=names,
    persons=persons,
    max_total=100
)

# Estimate learning impact
impact = learner.get_learning_impact_estimate(queue)
print(f"Labeling {len(queue)} examples will improve accuracy by ~{impact['estimated_accuracy_gain']:.2%}")
```

---

## Performance Monitoring

### What's Monitored

Track model accuracy across **ALL features**:

#### Duplicate Detector
- **Overall accuracy**: % of correct predictions
- **Name accuracy**: Performance when names were key factor
- **Place accuracy**: Performance when places were key factor
- **Date accuracy**: Performance when dates were key factor
- **Relationship accuracy**: Performance when relationships were key factor

#### Language Detector
- **Overall accuracy**: % of correct language predictions
- **Per-language accuracy**: Performance for each of 7 languages

#### Quality Classifier
- **Overall metrics**: Precision, recall, F1 score
- **Per-issue metrics**: Performance for each of 7 quality categories

### Data Drift Detection

Automatically detects when data distribution changes:

- Compares recent performance to historical
- Flags significant accuracy drops
- Recommends retraining when needed

### Usage

```python
from gedmerge.ml.monitoring import PerformanceMonitor

monitor = PerformanceMonitor()

# Get duplicate detector performance
perf = monitor.get_duplicate_detector_performance(time_window_days=30)

print(f"Overall accuracy: {perf['overall']['accuracy']:.1%}")
print(f"\nPer-feature accuracy:")
for feature, metrics in perf['by_feature'].items():
    if metrics['accuracy']:
        print(f"  {feature:15s}: {metrics['accuracy']:.1%} ({metrics['count']} cases)")

# Check for alerts
if 'alert' in perf:
    print(f"\n⚠️  {perf['alert']['level'].upper()}: {perf['alert']['message']}")
    print(f"   Recommendation: {perf['alert']['recommendation']}")

# Language detector performance
lang_perf = monitor.get_language_detector_performance()

print(f"\nLanguage detection accuracy: {lang_perf['overall']['accuracy']:.1%}")
for lang, metrics in lang_perf['by_language'].items():
    print(f"  {lang.upper()}: {metrics['accuracy']:.1%} ({metrics['count']} samples)")

# Detect data drift
drift = monitor.detect_data_drift("duplicate", comparison_days=30)
if drift['drift_detected']:
    print(f"⚠️  Data drift detected!")
    print(f"   {drift['recommendation']}")

# Comprehensive report
report = monitor.get_comprehensive_report()
```

---

## Automated Retraining

### Retraining Triggers

Models automatically retrain when:

1. **Performance Degradation**
   - Accuracy drops below 90% (warning)
   - Accuracy drops below 85% (critical)

2. **Sufficient New Feedback**
   - Duplicate detector: 50+ feedback instances
   - Language detector: 30+ corrections
   - Quality classifier: 50+ feedback instances

3. **Scheduled Intervals**
   - Minimum 7 days between retrains
   - Check daily for triggers

4. **Data Drift**
   - Significant change in data distribution detected

### Scheduler Usage

```python
from gedmerge.ml.monitoring import RetrainingScheduler

scheduler = RetrainingScheduler()

# Check if any models need retraining
decisions = scheduler.check_all_models()

for model_name, decision in decisions.items():
    if decision['should_retrain']:
        print(f"{model_name}: {decision['reason']}")

# Automatically retrain if needed
result = scheduler.auto_retrain_if_needed()

print(f"Models checked: {len(result['decisions'])}")
for model_name, model_result in result['results'].items():
    if model_result.get('status') == 'updated':
        print(f"✅ {model_name} updated to {model_result['new_version']}")
        print(f"   Trained on {model_result['num_samples']} new samples")

# Get schedule status
status = scheduler.get_retraining_schedule_status()
print(f"\nLast check: {status['last_check']}")
print(f"Retrain counts: {status['retrain_counts']}")
print(f"Next check recommended: {status['next_check_recommended']}")
```

### Cron Job Setup

For automated daily checks:

```bash
# Add to crontab
0 2 * * * cd /path/to/gedmerge && python -c "from gedmerge.ml.monitoring import RetrainingScheduler; RetrainingScheduler().auto_retrain_if_needed()"
```

---

## API Reference

### Feedback Submission

#### POST `/api/learning/feedback/duplicate`
Submit duplicate detection feedback

**Request:**
```json
{
  "person1_id": "I001",
  "person2_id": "I002",
  "predicted_duplicate": true,
  "predicted_confidence": 0.87,
  "user_confirmed": true,
  "model_version": "v1.0.0",
  "name_similarity": 0.92,
  "surname_match": true,
  "given_name_match": true,
  "phonetic_match": true,
  "birth_place_match": true,
  "death_place_match": false,
  "place_similarity": 0.75,
  "birth_date_match": true,
  "death_date_match": true,
  "date_conflict": false,
  "age_difference": 0,
  "shared_parents": 2,
  "shared_spouses": 0,
  "family_structure_match": true,
  "user_notes": "Same person, confirmed by marriage record",
  "correction_type": null
}
```

**Response:**
```json
{
  "status": "success",
  "feedback_id": 1234,
  "message": "Feedback recorded. Model will learn from this!"
}
```

#### POST `/api/learning/feedback/language`
Submit language detection correction

**Request:**
```json
{
  "name": "François Müller",
  "predicted_language": "de",
  "predicted_confidence": 0.65,
  "correct_language": "fr",
  "model_version": "v1.0.0",
  "place_context": "Strasbourg, France",
  "user_notes": "French name despite German surname"
}
```

### Performance Monitoring

#### GET `/api/learning/performance/duplicate-detector?days=30`
Get duplicate detector performance

**Response:**
```json
{
  "overall": {
    "accuracy": 0.9534,
    "total_predictions": 156,
    "correct_predictions": 149
  },
  "by_feature": {
    "names": {"accuracy": 0.96, "count": 142},
    "places": {"accuracy": 0.91, "count": 98},
    "dates": {"accuracy": 0.94, "count": 124},
    "relationships": {"accuracy": 0.89, "count": 67}
  },
  "time_window_days": 30,
  "timestamp": "2025-11-16T14:30:00"
}
```

#### GET `/api/learning/performance/comprehensive`
Get performance for all models

### Retraining

#### POST `/api/learning/retrain/duplicate-detector`
Manually trigger duplicate detector update

**Response:**
```json
{
  "status": "updated",
  "new_version": "v20251116_143015_incremental",
  "num_samples": 87,
  "metrics": {
    "accuracy": 0.9612,
    "precision": 0.9534,
    "recall": 0.9487,
    "f1": 0.9510
  },
  "strategy": "warm_start"
}
```

#### POST `/api/learning/retrain/auto`
Auto-check and retrain models that need updates

#### GET `/api/learning/retrain/schedule-status`
Get automated retraining schedule status

### Feedback Statistics

#### GET `/api/learning/feedback/stats`
Get statistics about collected feedback

**Response:**
```json
{
  "duplicate": 1247,
  "name_match": 423,
  "language": 156,
  "quality": 892,
  "place": 234,
  "event": 187,
  "duplicate_accuracy": 0.9534,
  "name_match_accuracy": 0.9189,
  "language_accuracy": 0.9423
}
```

---

## Usage Examples

### End-to-End Workflow

```python
from gedmerge.ml.feedback import FeedbackDatabase, DuplicateFeedback
from gedmerge.ml.training.incremental_trainer import IncrementalTrainer
from gedmerge.ml.monitoring import PerformanceMonitor, RetrainingScheduler
from gedmerge.ml.active_learning import ActiveLearner
from gedmerge.ml.models import DuplicateDetectionModel
from datetime import datetime

# 1. Make a prediction
model = DuplicateDetectionModel.load("models/saved/duplicate_detector/v1.0.0/model.pkl")
prediction = model.predict(person1, person2)

print(f"Prediction: {'Duplicate' if prediction.is_duplicate else 'Not duplicate'}")
print(f"Confidence: {prediction.confidence:.1%}")

# 2. User reviews and provides feedback
user_decision = input("Are these duplicates? (y/n): ").lower() == 'y'

# 3. Submit feedback
feedback_db = FeedbackDatabase()

feedback = DuplicateFeedback(
    person1_id=str(person1.person_id),
    person2_id=str(person2.person_id),
    predicted_duplicate=prediction.is_duplicate,
    predicted_confidence=prediction.confidence,
    user_confirmed=user_decision,
    model_version="v1.0.0",
    timestamp=datetime.now().isoformat(),
    # Extract all feature values from prediction
    name_similarity=prediction.feature_importances.get('name_similarity', 0),
    # ... (all other features)
)

feedback_id = feedback_db.add_duplicate_feedback(feedback)
print(f"✅ Feedback recorded (ID: {feedback_id})")

# 4. Monitor performance
monitor = PerformanceMonitor(feedback_db)
performance = monitor.get_duplicate_detector_performance()

print(f"\nCurrent accuracy: {performance['overall']['accuracy']:.1%}")

# 5. Check if retraining needed
scheduler = RetrainingScheduler(feedback_db)
decisions = scheduler.check_all_models()

if decisions['duplicate_detector']['should_retrain']:
    print(f"\n⚡ Retraining needed: {decisions['duplicate_detector']['reason']}")

    # 6. Retrain automatically
    result = scheduler.auto_retrain_if_needed()

    if result['results'].get('duplicate_detector', {}).get('status') == 'updated':
        print(f"✅ Model updated to {result['results']['duplicate_detector']['new_version']}")
        print(f"   New accuracy: {result['results']['duplicate_detector']['metrics']['accuracy']:.1%}")

# 7. Use active learning to find uncertain cases
learner = ActiveLearner(duplicate_model=model)

uncertain_cases = learner.find_uncertain_duplicates(
    all_person_pairs,
    max_results=20
)

print(f"\nFound {len(uncertain_cases)} uncertain cases for review:")
for i, case in enumerate(uncertain_cases[:5], 1):
    print(f"{i}. Confidence: {case.confidence:.1%} - {case.suggested_action}")
```

### Continuous Improvement Loop

```python
import time

def continuous_learning_loop():
    """Run continuous learning loop."""
    scheduler = RetrainingScheduler()

    while True:
        print("Checking for retraining needs...")

        # Auto-retrain if needed
        result = scheduler.auto_retrain_if_needed()

        # Log results
        for model_name, model_result in result.get('results', {}).items():
            if model_result.get('status') == 'updated':
                print(f"✅ {model_name} updated!")

        # Wait 24 hours
        time.sleep(86400)

# Run in background
continuous_learning_loop()
```

---

## Best Practices

### 1. Feedback Quality

✅ **DO:**
- Provide detailed feedback when you're certain
- Add notes explaining your decision
- Indicate which feature was wrong (name/date/place)

❌ **DON'T:**
- Submit feedback when you're unsure
- Guess - it's better to skip uncertain cases

### 2. Review Frequency

- Review **uncertain predictions first** (active learning)
- Aim for **10-20 feedback items per day**
- Prioritize high-impact corrections

### 3. Retraining Schedule

- **Check daily** for retraining triggers
- **Retrain weekly** even if no triggers
- **Monitor performance** after each update

### 4. Model Version Management

- Keep **last 3 versions** of each model
- **Compare versions** before deploying
- **Rollback** if new version performs worse

### 5. Data Coverage

Ensure feedback covers all aspects:
- ✅ Various name types (surnames, given names)
- ✅ Different places (cities, countries, regions)
- ✅ Date ranges (historical to recent)
- ✅ Relationship types (parents, spouses, children)

---

## Troubleshooting

### Low Accuracy After Update

**Problem**: Model accuracy decreased after retraining

**Solutions:**
1. Check feedback quality - remove outliers
2. Ensure balanced feedback (not all positive or all negative)
3. Rollback to previous version
4. Wait for more feedback samples

### Insufficient Feedback

**Problem**: Not enough feedback to trigger retraining

**Solutions:**
1. Lower `min_new_samples` threshold
2. Use active learning to prioritize review
3. Combine multiple databases for more data
4. Wait longer before retraining

### Performance Degradation

**Problem**: Model accuracy declining over time

**Solutions:**
1. Check for data drift (monitor.detect_data_drift())
2. Verify feedback is representative
3. Retrain from scratch with all historical data
4. Adjust retraining thresholds

---

## Future Enhancements

- [ ] Web UI for feedback submission
- [ ] Automated active learning suggestions in dashboard
- [ ] A/B testing framework for model comparison
- [ ] SHAP explanations for predictions
- [ ] Multi-user feedback aggregation
- [ ] Confidence calibration
- [ ] Transfer learning from other databases

---

## Credits

Developed for GedMerge genealogy system.

**Techniques Used:**
- Incremental Learning (online ML)
- Active Learning (uncertainty sampling)
- Performance Monitoring
- Automated Retraining

**References:**
- Settles, B. (2009). Active Learning Literature Survey
- Losing, V., et al. (2018). Incremental On-Line Learning: A Review
- Gama, J., et al. (2014). A Survey on Concept Drift Adaptation

---

## Summary

GedMerge's continual learning system transforms static ML models into **living, adaptive systems** that improve from every user interaction.

**Key Features:**
- ✅ Captures feedback on **all aspects**: names, places, events, relationships
- ✅ **Incremental updates** without full retraining
- ✅ **Active learning** prioritizes valuable examples
- ✅ **Performance monitoring** across all features
- ✅ **Automated retraining** when needed

**Result**: A genealogy system that becomes an expert on **YOUR** data over time! 🚀
