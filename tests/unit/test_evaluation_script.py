from scripts import run_evaluation


def test_evaluation_script_resolves_rag_service_from_app_state() -> None:
    assert run_evaluation.rag_service is run_evaluation.app.state.services.rag_service
