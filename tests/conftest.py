import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from tempfile import mkdtemp
from typing import Dict, Optional

import ape
import pytest
import yaml
from _pytest.runner import pytest_runtest_makereport as orig_pytest_runtest_makereport
from ape.api.networks import LOCAL_NETWORK_NAME
from ape.contracts import ContractContainer
from ape.managers.config import CONFIG_FILE_NAME
from ethpm_types import ContractType

from ape_hardhat import HardhatForkProvider, HardhatProvider

# NOTE: Ensure that we don't use local paths for the DATA FOLDER
ape.config.DATA_FOLDER = Path(mkdtemp()).resolve()

BASE_CONTRACTS_PATH = Path(__file__).parent / "data" / "contracts"

# Needed to test tracing support in core `ape test` command.
pytest_plugins = ["pytester"]


def pytest_runtest_makereport(item, call):
    tr = orig_pytest_runtest_makereport(item, call)
    if call.excinfo is not None and "too many requests" in str(call.excinfo).lower():
        tr.outcome = "skipped"
        tr.wasxfail = "reason: Alchemy requests overloaded (likely in CI)"

    return tr


@pytest.fixture(scope="session", autouse=True)
def in_tests_dir(config):
    with config.using_project(Path(__file__).parent):
        yield


@pytest.fixture(scope="session")
def config():
    return ape.config


@pytest.fixture(scope="session")
def project():
    return ape.project


@pytest.fixture(scope="session")
def accounts():
    return ape.accounts.test_accounts


@pytest.fixture(scope="session")
def convert():
    return ape.convert


@pytest.fixture(scope="session")
def networks():
    return ape.networks


@pytest.fixture(scope="session")
def create_provider(local_network_api):
    def method():
        return HardhatProvider(
            name="hardhat",
            network=local_network_api,
            request_header={},
            data_folder=Path("."),
            provider_settings={},
        )

    return method


@pytest.fixture(scope="session", params=("solidity", "vyper"))
def raw_contract_type(request):
    path = BASE_CONTRACTS_PATH / "ethereum" / "local" / f"{request.param}_contract.json"
    return path.read_text()


@pytest.fixture(scope="session")
def contract_type(raw_contract_type) -> ContractType:
    return ContractType.parse_raw(raw_contract_type)


@pytest.fixture(scope="session")
def contract_container(contract_type) -> ContractContainer:
    return ContractContainer(contract_type=contract_type)


@pytest.fixture(scope="session")
def contract_instance(owner, contract_container, connected_provider):
    return owner.deploy(contract_container)


@pytest.fixture(scope="session")
def sender(accounts):
    return accounts[0]


@pytest.fixture(scope="session")
def receiver(accounts):
    return accounts[1]


@pytest.fixture(scope="session")
def owner(accounts):
    return accounts[2]


@pytest.fixture(scope="session")
def local_network_api(networks):
    return networks.ecosystems["ethereum"][LOCAL_NETWORK_NAME]


@pytest.fixture(scope="session")
def connected_provider(networks, local_network_api):
    with networks.parse_network_choice(
        "ethereum:local:hardhat", provider_settings={"port": "auto"}
    ) as provider:
        yield provider


@pytest.fixture(scope="session")
def disconnected_provider(create_provider):
    return create_provider()


@pytest.fixture(scope="session")
def create_fork_provider(networks):
    def method(port: int = 9001, network: str = "mainnet"):
        network_api = networks.ecosystems["ethereum"][f"{network}-fork"]
        provider = HardhatForkProvider(
            name="hardhat",
            network=network_api,
            request_header={},
            data_folder=Path("."),
            provider_settings={},
        )
        provider.port = port
        return provider

    return method


@pytest.fixture(scope="session")
def mainnet_fork_network_api(networks):
    return networks.ecosystems["ethereum"]["mainnet-fork"]


@pytest.fixture(scope="session")
def temp_config(config):
    @contextmanager
    def func(data: Dict, package_json: Optional[Dict] = None):
        with tempfile.TemporaryDirectory() as temp_dir_str:
            temp_dir = Path(temp_dir_str)

            config._cached_configs = {}
            config_file = temp_dir / CONFIG_FILE_NAME
            config_file.touch()
            config_file.write_text(yaml.dump(data))
            config.load(force_reload=True)

            if package_json:
                package_json_file = temp_dir / "package.json"
                package_json_file.write_text(json.dumps(package_json))

            with config.using_project(temp_dir):
                yield temp_dir

            config_file.unlink()
            config._cached_configs = {}

    return func
