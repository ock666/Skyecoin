import logging
from serpentcoin.storage import Database

logger = logging.getLogger(__name__)


def calculate_difficulty(db: Database, config) -> int:
    block_count = db.get_block_count()
    if block_count == 0:
        return config.difficulty

    if block_count % config.difficulty_adjust_interval != 0:
        last_block = db.get_last_block()
        if last_block:
            return last_block["difficulty"]
        return config.difficulty

    current_block = db.get_last_block()
    if not current_block:
        return config.difficulty

    epoch_start_index = max(1, block_count - config.difficulty_adjust_interval + 1)
    epoch_start_block = db.get_block(epoch_start_index)
    if not epoch_start_block:
        return current_block["difficulty"]

    actual_time = current_block["timestamp"] - epoch_start_block["timestamp"]
    expected_time = config.difficulty_adjust_interval * config.target_block_time

    current_diff = current_block["difficulty"]

    if actual_time < expected_time * 0.5:
        new_diff = current_diff + 1
        logger.info(
            "Difficulty increased: %d -> %d (too fast: %.0fs vs expected %.0fs)",
            current_diff, new_diff, actual_time, expected_time,
        )
        return new_diff
    elif actual_time > expected_time * 2.0:
        new_diff = max(1, current_diff - 1)
        logger.info(
            "Difficulty decreased: %d -> %d (too slow: %.0fs vs expected %.0fs)",
            current_diff, new_diff, actual_time, expected_time,
        )
        return new_diff
    else:
        logger.info(
            "Difficulty stable at %d (actual: %.0fs, expected: %.0fs)",
            current_diff, actual_time, expected_time,
        )
        return current_diff
