import pytest


class MethodRecorder:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return {"method": name, "args": args, "kwargs": kwargs}

        return method


class FakeSearchEngineClient:
    def __init__(self):
        self.cat = MethodRecorder()
        self.cluster = MethodRecorder()
        self.indices = MethodRecorder()
        self.calls = []

    def __getattr__(self, name):
        def method(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            return {"method": name, "args": args, "kwargs": kwargs}

        return method


def attach_fake_client(client_instance, engine_type="elasticsearch"):
    fake_client = FakeSearchEngineClient()
    client_instance.client = fake_client
    client_instance.engine_type = engine_type
    return fake_client


@pytest.fixture
def attach_client():
    return attach_fake_client


@pytest.fixture
def fake_response_processor(monkeypatch):
    def passthrough(self, response):
        return response

    return passthrough
