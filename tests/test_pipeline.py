from __future__ import annotations

from unittest.mock import patch

from src.pipeline import PipelineService


def test_pipeline_service_skips_overlapping_runs() -> None:
    service = PipelineService()
    assert service._run_lock.acquire(blocking=False)

    with patch("src.pipeline.execute_ingestion_cycle") as mock_execute:
        result = service.run_cycle_if_available(trigger_mode="scheduled")

    service._run_lock.release()
    assert result is None
    mock_execute.assert_not_called()


def test_pipeline_service_continues_after_failed_run() -> None:
    service = PipelineService()

    with patch("src.pipeline.execute_ingestion_cycle") as mock_execute:
        mock_execute.side_effect = [{"status": "failed"}, {"status": "success"}]
        first_result = service.run_cycle_if_available(trigger_mode="scheduled")
        result = service.run_cycle_if_available(trigger_mode="scheduled")

    assert first_result == {"status": "failed"}
    assert result == {"status": "success"}
    assert mock_execute.call_count == 2
