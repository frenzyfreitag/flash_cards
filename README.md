# World building flashcard Generator

A Python CLI that generates random world building prompts by combining categories.

## Installation

```bash
pipx install ~/personal/projects/flash_cards
cards --version
```

## Usage

```bash
# Initialize database
cards init --data-file data/initial_data.yaml

# Generate flashcard
cards gen
# Output: > mountain, medieval, elf

# Generate from specific categories
cards gen --cat "terrain,era"
# Output: > desert, ancient

# Generate from N random categories
cards gen --rand-cat 2
# Output: > plateau, elf

# Update from YAML (adds new categories/options)
cards update --data-file updated_data.yaml

# Set custom repeats for an option
cards set-reps 5 --cat terrain --opt mountain

# Reset repeats to 1
cards reset-reps --all
cards reset-reps --cat terrain

# Show version
cards --version
```

## Data Format

YAML file with categories and options:

```yaml
terrain:
  - mountain
  - desert
era:
  - medieval
  - cyberpunk
```

## Testing

```bash
cd ~/personal/projects/flash_cards
source .venv/bin/activate
pytest tests/ -v
```
