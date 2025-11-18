# GedMerge ML Quick Start Guide

Get started with machine learning in GedMerge in 5 minutes!

## Installation

```bash
# Clone repository
git clone https://github.com/yourusername/Python-Scripts.git
cd Python-Scripts/GedMerge

# Install with ML dependencies
pip install -e .

# Or with development tools
pip install -e ".[dev,ml]"
```

## Quick Demo

### 1. Start the Web Dashboard

```bash
# Start FastAPI server
python -m gedmerge.web.api.main

# Open browser to http://localhost:8000
```

You should see the GedMerge ML Dashboard with:
- 📊 Overview of system status
- 🤖 Registered ML models
- 🔮 Prediction tools
- 🎓 Training interface
- 🔍 Data quality analysis

### 2. Train Your First Model

#### Using the Web Dashboard

1. Navigate to the **Training** tab
2. Select "Duplicate Detector" from dropdown
3. Enter your database path: `/path/to/your/database.rmtree`
4. Click "Start Training"
5. Monitor progress in "Training Jobs" section

#### Using Python

```python
from gedmerge.ml.training import ModelTrainer
from gedmerge.ml.utils import MLConfig

# Initialize trainer
config = MLConfig()
trainer = ModelTrainer(config)

# Train duplicate detector
metrics = trainer.train_duplicate_detector(
    database_path="/path/to/database.rmtree",
    model_type="xgboost",
    version="v1.0.0"
)

print(f"✅ Training complete!")
print(f"Accuracy: {metrics['accuracy']:.2%}")
print(f"F1 Score: {metrics['f1']:.2%}")
```

Expected output:
```
Training Duplicate Detector...
Generating duplicate detection training data...
Found 1,234 high-confidence duplicate pairs
Generated 1,234 negative examples
Generated 308 hard negative examples
Total training pairs generated: 2,776

Training XGBoost duplicate detector...
Training samples: 2,776
Positive examples: 1,234
Negative examples: 1,542

Validation Results:
  accuracy: 0.9721
  precision: 0.9583
  recall: 0.9341
  f1: 0.9460
  roc_auc: 0.9892

Feature Importance:
  name_similarity                : 0.2847
  phonetic_similarity            : 0.2156
  birth_date_match               : 0.1523
  surname_similarity             : 0.1089
  ...

✅ Training complete!
Accuracy: 97.21%
F1 Score: 94.60%
```

### 3. Make Predictions

#### Name Matching

```python
from gedmerge.ml.models import NameMatchingModel

# Load pre-trained model (or train your own)
model = NameMatchingModel(model_type="transformer")
model.create_model()

# Compare two names
result = model.predict(
    "Jean-Baptiste Dubois",
    "John Baptist Dubois"
)

print(f"Similarity: {result.similarity:.2%}")
print(f"Is match: {'✅ Yes' if result.is_match else '❌ No'}")
```

Output:
```
Similarity: 87.32%
Is match: ✅ Yes
```

#### Language Detection

```python
from gedmerge.ml.models import LanguageDetectionModel

# Create and train model
model = LanguageDetectionModel(model_type="multinomial_nb")

# Or load pre-trained
# model = LanguageDetectionModel.load("models/saved/language_detector/v1.0.0/model.pkl")

# Detect language
names = [
    "François Müller",
    "Giovanni Rossi",
    "José García",
    "John Smith",
]

for name in names:
    lang, confidence = model.predict(name)
    print(f"{name:25s} → {lang.upper()} ({confidence:.1%})")
```

Output:
```
François Müller           → FR (96.2%)
Giovanni Rossi            → IT (94.8%)
José García               → ES (97.1%)
John Smith                → EN (91.3%)
```

#### Duplicate Detection

```python
from gedmerge.ml.models import DuplicateDetectionModel
from gedmerge.rootsmagic.adapter import RootsMagicDatabase

# Load model and database
model = DuplicateDetectionModel.load("models/saved/duplicate_detector/v1.0.0/model.pkl")
db = RootsMagicDatabase("/path/to/database.rmtree")

# Get two persons
person1 = db.get_person("I001")
person2 = db.get_person("I002")

# Check if duplicates
prediction = model.predict(person1, person2)

print(f"Is duplicate: {prediction.is_duplicate}")
print(f"Confidence: {prediction.confidence:.2%}")
print("\nTop contributing features:")
for feature, importance in sorted(
    prediction.feature_importances.items(),
    key=lambda x: -x[1]
)[:5]:
    print(f"  {feature:30s}: {importance:.2%}")
```

Output:
```
Is duplicate: True
Confidence: 94.73%

Top contributing features:
  name_similarity                : 28.47%
  phonetic_similarity            : 21.56%
  birth_date_match               : 15.23%
  surname_similarity             : 10.89%
  birth_place_similarity         : 8.42%
```

#### Data Quality Check

```python
from gedmerge.ml.models import DataQualityClassifier
from gedmerge.rootsmagic.adapter import RootsMagicDatabase

# Load model
model = DataQualityClassifier.load("models/saved/quality_classifier/v1.0.0/model.pkl")

# Load database
db = RootsMagicDatabase("/path/to/database.rmtree")
person = db.get_person("I123")

# Check quality issues
issues = model.get_quality_issues(person, threshold=0.5)

if issues:
    print(f"⚠️  Quality issues found for {person.names[0]}:")
    for issue in issues:
        print(f"  - {issue.replace('_', ' ').title()}")
else:
    print(f"✅ No quality issues found for {person.names[0]}")

# Get detailed predictions
predictions = model.predict(person)
print("\nDetailed quality scores:")
for category, prob in sorted(predictions.items(), key=lambda x: -x[1]):
    if prob > 0.3:
        print(f"  {category:30s}: {prob:.1%}")
```

Output:
```
⚠️  Quality issues found for John /Smith/:
  - Missing Data
  - Placeholder Name

Detailed quality scores:
  placeholder_name              : 87.3%
  missing_data                  : 62.4%
  inconsistent_formatting       : 34.1%
```

### 4. Generate Quality Report

```python
from gedmerge.ml.models import DataQualityClassifier
from gedmerge.rootsmagic.adapter import RootsMagicDatabase

# Load model and all persons
model = DataQualityClassifier.load("models/saved/quality_classifier/v1.0.0/model.pkl")
db = RootsMagicDatabase("/path/to/database.rmtree")
all_persons = list(db.get_all_persons())

# Generate comprehensive report
report = model.generate_quality_report(all_persons, threshold=0.5)

print(f"""
📊 Data Quality Report
{'='*60}
Total persons:              {report['total_persons']:,}
Persons with issues:        {report['persons_with_issues']:,}
Avg issues per person:      {report['avg_issues_per_person']:.2f}
Max issues per person:      {report['max_issues_per_person']}

Top Quality Issues:
""")

for category, count in sorted(report['issue_counts'].items(), key=lambda x: -x[1])[:7]:
    pct = report['issue_percentages'][category]
    bar = '█' * int(pct / 2)
    print(f"  {category:30s}: {count:5,} ({pct:5.1f}%) {bar}")
```

Output:
```
📊 Data Quality Report
============================================================
Total persons:              61,024
Persons with issues:        12,847
Avg issues per person:      0.47
Max issues per person:      4

Top Quality Issues:
  missing_data                  : 5,234 (  8.6%) ████
  placeholder_name              : 3,891 (  6.4%) ███
  inconsistent_formatting       : 2,156 (  3.5%) █
  titles_in_wrong_field         : 1,243 (  2.0%) █
  invalid_dates                 :   892 (  1.5%)
  embedded_variants             :   321 (  0.5%)
  reversed_names                :   110 (  0.2%)
```

## API Usage

### REST API

All models are accessible via REST API when the web server is running.

```bash
# Start server
python -m gedmerge.web.api.main
```

```python
import requests

# Check name similarity
response = requests.post('http://localhost:8000/api/predict/name-match', json={
    'name1': 'Jean-Baptiste Dubois',
    'name2': 'John Baptist Dubois'
})

result = response.json()
print(f"Similarity: {result['similarity']:.2%}")

# Detect language
response = requests.post('http://localhost:8000/api/predict/language', json={
    'name': 'François Müller'
})

result = response.json()
print(f"Language: {result['language']} ({result['confidence']:.1%})")

# Check duplicate (requires database access)
response = requests.post('http://localhost:8000/api/predict/duplicate', json={
    'person1_id': 'I001',
    'person2_id': 'I002',
    'database_path': '/path/to/database.rmtree'
})

result = response.json()
print(f"Is duplicate: {result['is_duplicate']}")
print(f"Confidence: {result['confidence']:.2%}")
```

## Configuration

Customize ML behavior by modifying `MLConfig`:

```python
from gedmerge.ml.utils import MLConfig

config = MLConfig(
    # General settings
    batch_size=32,
    learning_rate=0.001,
    num_epochs=100,
    early_stopping_patience=10,
    random_seed=42,

    # Model storage
    model_dir="models/saved",
    cache_dir="models/cache",
)

# Customize duplicate detector
config.duplicate_detector_config = {
    'model_type': 'xgboost',  # or 'lightgbm', 'random_forest'
    'n_estimators': 200,      # More trees = better accuracy
    'max_depth': 8,           # Deeper = more complex
    'learning_rate': 0.1,
    'min_confidence_threshold': 60.0,
    'high_confidence_threshold': 85.0,
}

# Customize name matcher
config.name_matching_config = {
    'model_type': 'siamese',  # or 'transformer'
    'embedding_dim': 128,
    'hidden_dim': 256,
    'dropout': 0.3,
    'margin': 1.0,
}

# Use custom config
from gedmerge.ml.training import ModelTrainer
trainer = ModelTrainer(config)
```

## Next Steps

1. **Read Full Documentation**: See `ML_DOCUMENTATION.md` for comprehensive guide
2. **Explore Web Dashboard**: Navigate all tabs to discover features
3. **Train All Models**: Build complete ML suite for your database
4. **Integrate with Workflow**: Use models in your duplicate detection pipeline
5. **Monitor Performance**: Track model metrics over time
6. **Fine-tune**: Adjust configuration for your specific data

## Common Workflows

### Workflow 1: Find and Review Duplicates

```python
from gedmerge.ml.models import DuplicateDetectionModel
from gedmerge.rootsmagic.adapter import RootsMagicDatabase

# 1. Load model and database
model = DuplicateDetectionModel.load("models/saved/duplicate_detector/v1.0.0/model.pkl")
db = RootsMagicDatabase("family.rmtree")

# 2. Get all persons
all_persons = list(db.get_all_persons())

# 3. Find duplicates
duplicates = []
for i in range(len(all_persons)):
    for j in range(i + 1, len(all_persons)):
        pred = model.predict(all_persons[i], all_persons[j])

        if pred.is_duplicate and pred.confidence > 0.85:
            duplicates.append({
                'person1': all_persons[i],
                'person2': all_persons[j],
                'confidence': pred.confidence,
            })

# 4. Review top matches
print(f"Found {len(duplicates)} high-confidence duplicates\n")

for dup in sorted(duplicates, key=lambda x: -x['confidence'])[:10]:
    p1 = dup['person1']
    p2 = dup['person2']

    print(f"Confidence: {dup['confidence']:.1%}")
    print(f"  Person 1: {p1.names[0]} (ID: {p1.person_id})")
    print(f"  Person 2: {p2.names[0]} (ID: {p2.person_id})")
    print()
```

### Workflow 2: Clean Up Data Quality

```python
from gedmerge.ml.models import DataQualityClassifier
from gedmerge.rootsmagic.adapter import RootsMagicDatabase

# Load model and database
model = DataQualityClassifier.load("models/saved/quality_classifier/v1.0.0/model.pkl")
db = RootsMagicDatabase("family.rmtree")

# Get persons with quality issues
all_persons = list(db.get_all_persons())
persons_with_issues = []

for person in all_persons:
    issues = model.get_quality_issues(person, threshold=0.5)
    if issues:
        persons_with_issues.append((person, issues))

# Sort by number of issues
persons_with_issues.sort(key=lambda x: -len(x[1]))

# Review and fix
print(f"Found {len(persons_with_issues)} persons with quality issues\n")
print("Top 20 persons to review:\n")

for person, issues in persons_with_issues[:20]:
    print(f"{person.names[0] if person.names else 'Unknown'} (ID: {person.person_id})")
    for issue in issues:
        print(f"  ⚠️  {issue.replace('_', ' ').title()}")
    print()
```

## Troubleshooting

**Problem**: ModuleNotFoundError
**Solution**: Install dependencies
```bash
pip install -e ".[ml]"
```

**Problem**: CUDA out of memory
**Solution**: Use CPU or reduce batch size
```python
model = NameMatchingModel(device="cpu")
config.batch_size = 16
```

**Problem**: Training takes too long
**Solution**: Start with smaller dataset or reduce epochs
```python
config.num_epochs = 50  # Instead of 100
# Or sample database
persons_sample = random.sample(all_persons, 10000)
```

**Problem**: Low accuracy
**Solution**: Get more training data or adjust thresholds
```python
# Generate more training pairs
labeled_pairs = data_gen.generate_duplicate_pairs(
    high_confidence_threshold=85.0,  # Lower threshold
    num_pairs=5000,  # More pairs
)
```

## Support

- 📖 Full Documentation: `ML_DOCUMENTATION.md`
- 🐛 Issues: GitHub Issues
- 💬 Discussions: GitHub Discussions
- 📧 Email: support@gedmerge.com

---

Happy genealogy research! 🧬
