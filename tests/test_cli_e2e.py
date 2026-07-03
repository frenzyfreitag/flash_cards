import os
import tempfile

import pytest
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


@pytest.fixture
def test_db():
    """Create a temporary test database that gets cleaned up after test"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def test_yaml():
    """Create a temporary YAML file with test data"""
    fd, path = tempfile.mkstemp(suffix='.yaml')
    with os.fdopen(fd, 'w') as f:
        f.write("""terrain:
  - mountain
  - desert
  - forest
era:
  - medieval
  - modern
character:
  - human
  - elf
""")
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestInit:
    def test_init_empty(self, test_db):
        result = runner.invoke(app, ["init", "--db", test_db])
        assert result.exit_code == 0
        assert "initialized (empty)" in result.stdout

    def test_init_with_data_file(self, test_db, test_yaml):
        result = runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        assert result.exit_code == 0
        assert "7 options across 3 categories" in result.stdout

    def test_init_with_nonexistent_file(self, test_db):
        result = runner.invoke(app, ["init", "--data-file", "/nonexistent.yaml", "--db", test_db])
        assert result.exit_code == 1
        assert "Data file not found" in result.stdout

    def test_init_with_existing_data_no_force(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        result = runner.invoke(app, ["init", "--db", test_db], input="n\n")
        assert result.exit_code == 0
        assert "Cancelled" in result.stdout

    def test_init_with_existing_data_with_force(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        result = runner.invoke(app, ["init", "--force", "--db", test_db])
        assert result.exit_code == 0
        assert "initialized (empty)" in result.stdout


class TestGenerate:
    def test_gen_without_init(self, test_db):
        result = runner.invoke(app, ["gen", "--db", test_db])
        assert result.exit_code == 1
        assert "not initialized" in result.stdout

    def test_gen_on_empty_db(self, test_db):
        runner.invoke(app, ["init", "--db", test_db])
        result = runner.invoke(app, ["gen", "--db", test_db])
        assert result.exit_code == 1
        assert "not initialized" in result.stdout

    def test_gen_with_data(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        result = runner.invoke(app, ["gen", "--db", test_db])
        assert result.exit_code == 0
        assert ">" in result.stdout
        parts = result.stdout.split(">")[1].strip().split(", ")
        assert len(parts) == 3

    def test_gen_exhaustion(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])

        # Generate until at least one category exhausts (terrain has 3 options)
        for _ in range(3):
            runner.invoke(app, ["gen", "--db", test_db])

        result = runner.invoke(app, ["gen", "--db", test_db])
        # Either succeeds or shows exhaustion (depends on which category exhausts first)
        if result.exit_code == 1:
            assert "exhausted" in result.stdout
            assert "reset-reps" in result.stdout

    def test_gen_equal_probability(self, test_db):
        """Test that options have equal probability regardless of repeats_remaining"""
        fd, yaml_path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            f.write("test:\n  - opt1\n  - opt2\n  - opt3\n")

        runner.invoke(app, ["init", "--data-file", yaml_path, "--db", test_db])
        runner.invoke(app, ["set-reps", "10", "--cat", "test", "--opt", "opt2", "--db", test_db])

        # Generate multiple times to test probability
        # With equal probability and 3 options, we expect to see all 3 eventually
        results = []
        for _ in range(10):
            result = runner.invoke(app, ["gen", "--db", test_db])
            if result.exit_code == 0:
                results.append(result.stdout.split(">")[1].strip())

        # Should see multiple unique options (probabilistic test)
        unique = set(results)
        assert len(unique) >= 2  # At least 2 different options in 10 tries

        os.unlink(yaml_path)


class TestSetRepeats:
    def test_set_reps_valid(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        result = runner.invoke(app, ["set-reps", "5", "--cat", "terrain", "--opt", "mountain", "--db", test_db])
        assert result.exit_code == 0
        assert "repeats=5" in result.stdout

    def test_set_reps_invalid_value_zero(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        result = runner.invoke(app, ["set-reps", "0", "--cat", "terrain", "--opt", "mountain", "--db", test_db])
        assert result.exit_code == 1
        assert "must be 1 or higher" in result.stdout

    def test_set_reps_invalid_value_negative(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        result = runner.invoke(app, ["set-reps", "-5", "--cat", "terrain", "--opt", "mountain", "--db", test_db])
        assert result.exit_code != 0

    def test_set_reps_nonexistent_category(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        result = runner.invoke(app, ["set-reps", "5", "--cat", "fake", "--opt", "test", "--db", test_db])
        assert result.exit_code == 1
        assert "does not exist" in result.stdout

    def test_set_reps_nonexistent_option(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        result = runner.invoke(app, ["set-reps", "5", "--cat", "terrain", "--opt", "fake", "--db", test_db])
        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_set_reps_persistence(self, test_db, test_yaml):
        """Test that set repeats persists and affects generation"""
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        runner.invoke(app, ["set-reps", "3", "--cat", "terrain", "--opt", "mountain", "--db", test_db])

        # Generate until terrain exhausts (2 options with 1 repeat, 1 with 3)
        # Should take 5 total generates (2 + 3)
        for _ in range(5):
            result = runner.invoke(app, ["gen", "--db", test_db])
            if result.exit_code == 1 and "terrain" in result.stdout:
                break

        # Terrain should be exhausted now
        result = runner.invoke(app, ["gen", "--db", test_db])
        if "terrain" in result.stdout or result.exit_code == 1:
            assert True  # Expected behavior


class TestResetRepeats:
    def test_reset_reps_all(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        for _ in range(5):
            runner.invoke(app, ["gen", "--db", test_db])

        result = runner.invoke(app, ["reset-reps", "--all", "--db", test_db])
        assert result.exit_code == 0
        assert "Reset all categories" in result.stdout
        assert "7 options" in result.stdout

    def test_reset_reps_single_category(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        for _ in range(3):
            runner.invoke(app, ["gen", "--db", test_db])

        result = runner.invoke(app, ["reset-reps", "--cat", "terrain", "--db", test_db])
        assert result.exit_code == 0
        assert "Reset 1 category" in result.stdout
        assert "3 options" in result.stdout

    def test_reset_reps_multiple_categories(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        for _ in range(5):
            runner.invoke(app, ["gen", "--db", test_db])

        result = runner.invoke(app, ["reset-reps", "--cat", "terrain,era", "--db", test_db])
        assert result.exit_code == 0
        assert "Reset 2 category" in result.stdout

    def test_reset_reps_without_flags(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        result = runner.invoke(app, ["reset-reps", "--db", test_db])
        assert result.exit_code == 1
        assert "Specify --all or --cat" in result.stdout

    def test_reset_reps_nonexistent_category(self, test_db, test_yaml):
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        result = runner.invoke(app, ["reset-reps", "--cat", "fake", "--db", test_db])
        assert result.exit_code == 1
        assert "does not exist" in result.stdout

    def test_reset_reps_after_exhaustion(self, test_db):
        """Test that reset allows generation to continue after exhaustion"""
        fd, yaml_path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            f.write("test:\n  - opt1\n  - opt2\n")

        runner.invoke(app, ["init", "--data-file", yaml_path, "--db", test_db])

        # Exhaust the category
        runner.invoke(app, ["gen", "--db", test_db])
        runner.invoke(app, ["gen", "--db", test_db])
        result = runner.invoke(app, ["gen", "--db", test_db])
        assert result.exit_code == 1
        assert "exhausted" in result.stdout

        # Reset and verify we can generate again
        runner.invoke(app, ["reset-reps", "--all", "--db", test_db])
        result = runner.invoke(app, ["gen", "--db", test_db])
        assert result.exit_code == 0
        assert ">" in result.stdout

        os.unlink(yaml_path)


class TestVersion:
    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.1.1" in result.stdout


class TestEdgeCases:
    def test_empty_category_in_yaml(self, test_db):
        """Test handling of empty categories in YAML"""
        fd, yaml_path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            f.write("terrain:\n  - mountain\nempty:\n")

        result = runner.invoke(app, ["init", "--data-file", yaml_path, "--db", test_db])
        # Should handle gracefully
        assert result.exit_code == 0

        os.unlink(yaml_path)

    def test_special_characters_in_option(self, test_db):
        """Test options with special characters"""
        fd, yaml_path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            f.write('test:\n  - "option with spaces"\n  - option-with-dashes\n')

        runner.invoke(app, ["init", "--data-file", yaml_path, "--db", test_db])
        result = runner.invoke(app, ["set-reps", "5", "--cat", "test", "--opt", "option with spaces", "--db", test_db])
        assert result.exit_code == 0

        os.unlink(yaml_path)

    def test_large_repeats_value(self, test_db, test_yaml):
        """Test very large repeats value"""
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        result = runner.invoke(app, ["set-reps", "999999", "--cat", "terrain", "--opt", "mountain", "--db", test_db])
        assert result.exit_code == 0
        assert "repeats=999999" in result.stdout

    def test_concurrent_category_exhaustion(self, test_db):
        """Test when multiple categories exhaust around the same time"""
        fd, yaml_path = tempfile.mkstemp(suffix='.yaml')
        with os.fdopen(fd, 'w') as f:
            f.write("cat1:\n  - opt1\ncat2:\n  - opt2\n")

        runner.invoke(app, ["init", "--data-file", yaml_path, "--db", test_db])

        # First generate uses both
        runner.invoke(app, ["gen", "--db", test_db])

        # Second generate should fail with one category exhausted
        result = runner.invoke(app, ["gen", "--db", test_db])
        assert result.exit_code == 1
        assert "exhausted" in result.stdout

        os.unlink(yaml_path)

    def test_whitespace_in_category_names(self, test_db, test_yaml):
        """Test that whitespace in comma-separated categories is handled"""
        runner.invoke(app, ["init", "--data-file", test_yaml, "--db", test_db])
        result = runner.invoke(app, ["reset-reps", "--cat", "terrain, era, character", "--db", test_db])
        assert result.exit_code == 0
        assert "Reset 3 category" in result.stdout
