# Public Character Dataset Workflow

This is the current recommended training path for InkPi competition models.

## Why this workflow

The old `data/real` pipeline can download a style-labeled calligraphy dataset, but that dataset is not suitable for the current Siamese matching task. It is useful for style classification research, not for template-vs-character matching.

The new recommended path is:

1. Use a character-labeled public calligraphy dataset.
2. Convert it into the InkPi training layout.
3. Run dataset audit before every training job.
4. Train the Siamese model only on matched character pairs.

## Recommended source

Public GitHub dataset:

- Repository: `zhuojg/chinese-calligraphy-dataset`
- Content: folder-per-character calligraphy images

Recommended server layout:

```text
~/datasets/zhuojg/character_dataset/chinese-calligraphy-dataset/chinese-calligraphy-dataset
```

## Convert the dataset

```bash
cd ~/src/InkPi-Raspberry-Pi
. venv/bin/activate

python3 training/prepare_character_dataset.py \
  --input ~/datasets/zhuojg/character_dataset/chinese-calligraphy-dataset/chinese-calligraphy-dataset \
  --output data/public_character \
  --clear-output \
  --min-images-per-char 4 \
  --max-images-per-char 24
```

This creates:

```text
data/public_character/
|-- originals/
|-- good/
|-- medium/
|-- poor/
`-- manifest.json
```

## Audit before training

```bash
cd ~/src/InkPi-Raspberry-Pi
. venv/bin/activate

python3 training/audit_dataset.py \
  --data data/public_character \
  --strict \
  --min-match-ratio 0.95 \
  --min-matched-samples 1000
```

If audit fails, do not start training. Fix the dataset first.

## Smoke training command

```bash
cd ~/src/InkPi-Raspberry-Pi
. venv/bin/activate

PYTHONIOENCODING=utf-8 python3 training/train_siamese.py \
  --data data/public_character \
  --epochs 1 \
  --batch-size 64 \
  --workers 2 \
  --device cuda \
  --pretrained \
  --amp \
  --min-match-ratio 0.95 \
  --min-matched-samples 1000
```

## Full V100 training command

```bash
cd ~/src/InkPi-Raspberry-Pi

DATA_SOURCE=public_character \
DATA_DIR=~/src/InkPi-Raspberry-Pi/data/public_character \
EPOCHS=30 \
BATCH_SIZE=128 \
NUM_WORKERS=8 \
USE_PRETRAINED=1 \
USE_AMP=1 \
bash training/train_v100.sh
```

## Current baseline from the V100 smoke test

Measured on `2026-03-25` on server `192.168.0.171`:

- dataset: `6290` characters
- matched samples: `121419`
- train pairs: `194270`
- val pairs: `48568`
- smoke run: `1 epoch`
- result: `train_acc=0.7439`, `val_acc=0.7543`

These numbers are much more believable than the old fake-perfect validation results from the style-labeled dataset.
