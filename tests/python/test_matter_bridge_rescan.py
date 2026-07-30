from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAIN_CPP = PROJECT_ROOT / "src" / "cpp" / "matter_bridge" / "main.cpp"
BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "build-matter-bridge.sh"
CONFIG_H = PROJECT_ROOT / "src" / "cpp" / "matter_bridge" / "CHIPProjectConfig.h"
APP_CONFIG_H = PROJECT_ROOT / "src" / "cpp" / "matter_bridge" / "CHIPProjectAppConfig.h"


def test_rescan_does_not_restart_commissioned_bridge_on_device_count_change() -> None:
    source = MAIN_CPP.read_text(encoding="utf-8")

    assert "exit(0)" not in source
    assert "keeping existing Matter endpoints stable" in source


def test_named_debug_bridge_uses_four_dynamic_devices_and_project_config() -> None:
    source = MAIN_CPP.read_text(encoding="utf-8")
    script = BUILD_SCRIPT.read_text(encoding="utf-8")
    config = CONFIG_H.read_text(encoding="utf-8")
    app_config = APP_CONFIG_H.read_text(encoding="utf-8")

    assert "kMaxDynamicDevices    = 4" in source
    assert "CHIPProjectAppConfig.h" in script
    assert "examples/tv-app/tv-common/include/CHIPProjectAppConfig.h" not in script
    assert 'chip_project_config_include="<CHIPProjectConfig.h>"' in script
    assert 'chip_project_config_include_dirs=["//include"]' in script
    assert '$CHIP_BRIDGE_DIR/include/CHIPProjectConfig.h' in script
    assert '$CHIP_BRIDGE_DIR/include/CHIPProjectAppConfig.h' in script
    assert "CHIP_SYSTEM_CONFIG_PACKETBUFFER_POOL_SIZE 0" in config
    assert "CHIP_SYSTEM_CONFIG_PACKETBUFFER_CAPACITY_MAX 9050" in config
    assert "CHIP_SYSTEM_CONFIG_PACKETBUFFER_CAPACITY_MAX >= 9050" in source
    assert "CHIP_DEVICE_CONFIG_DYNAMIC_ENDPOINT_COUNT 16" in app_config


def test_bridge_build_prunes_stock_zap_model_for_home_subscriptions() -> None:
    script = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "Pruning bridge ZAP model" in script
    assert "ROOT_CLUSTERS = {29, 31, 40, 48, 49, 60, 62, 63}" in script
    assert "AGGREGATOR_CLUSTERS = {3, 29}" in script
    assert "19, 21, 22" not in script

    # Pruning is cluster-level only. Attribute-level pruning was tried and
    # reverted: dropping NOCs/Fabrics/TrustedRootCertificates from
    # OperationalCredentials made Apple Home's post-CommissioningComplete read of
    # the Fabrics list (0x3E/0x0001) return UnsupportedAttribute, so the iPhone
    # aborted with "Pairing failed" and sent RemoveFabric. Oversized wildcard
    # reports are handled by the report-chunking patch below instead.
    assert "do NOT prune individual attributes" in script
    assert "OPCREDS_ATTRS" not in script
    assert "BASIC_ATTRS" not in script
    assert 'attr.get("code")' not in script
    assert "Bounding CHIP report chunks" in script
    assert "kMaxAttributesPerReportChunk = 8" in script
    assert "if (attributesRead > kMaxAttributesPerReportChunk)" in script
    assert "src/app/reporting/Engine.cpp" in script
    assert 'endpoint.get("endpointId") in (0, 1)' in script
    assert "bridge-app.zap" in script


def test_bridge_sync_client_uses_short_http_timeouts() -> None:
    source = (PROJECT_ROOT / "src" / "cpp" / "matter_bridge" / "SyncClient.cpp").read_text(
        encoding="utf-8"
    )

    assert "CURLOPT_CONNECTTIMEOUT_MS, 500L" in source
    assert "CURLOPT_TIMEOUT_MS, 2000L" in source
    assert "CURLOPT_TIMEOUT, 5L" not in source


def test_bridge_has_noop_init_stubs_for_pruned_stock_clusters() -> None:
    source = MAIN_CPP.read_text(encoding="utf-8")

    for symbol in (
        "MatterDiagnosticLogsPluginServerInitCallback",
        "MatterEthernetNetworkDiagnosticsPluginServerInitCallback",
        "MatterGeneralDiagnosticsPluginServerInitCallback",
        "MatterLevelControlPluginServerInitCallback",
        "MatterLocalizationConfigurationPluginServerInitCallback",
        "MatterOnOffPluginServerInitCallback",
        "MatterSoftwareDiagnosticsPluginServerInitCallback",
        "MatterSwitchPluginServerInitCallback",
        "MatterThreadNetworkDiagnosticsPluginServerInitCallback",
        "MatterTimeFormatLocalizationPluginServerInitCallback",
        "MatterUserLabelPluginServerInitCallback",
        "MatterWiFiNetworkDiagnosticsPluginServerInitCallback",
    ):
        assert f"void {symbol}() {{}}" in source


def test_bridge_registers_runtime_onoff_command_handler_for_dynamic_endpoints() -> None:
    source = MAIN_CPP.read_text(encoding="utf-8")

    assert "class DynamicOnOffCommandHandler" in source
    assert "RegisterCommandHandler(&gDynamicOnOffCommandHandler)" in source
    assert "UnregisterCommandHandler(&gDynamicOnOffCommandHandler)" in source
    assert "OnOff::Commands::On::Id" in source
    assert "OnOff::Commands::Off::Id" in source
    assert "OnOff::Commands::Toggle::Id" in source
    # Commands arriving over the Interaction Model must notify subscribers;
    # the ember write path passes notify_subscribers=false to avoid recursing.
    assert "HandleOnOffCommand(endpoint, true, /*notify_subscribers=*/true)" in source
    assert "HandleOnOffCommand(endpoint, false, /*notify_subscribers=*/true)" in source
    assert "HandleOnOffCommand(endpoint, on, /*notify_subscribers=*/false)" in source


def test_bridge_exposes_stable_unique_id_for_each_bridged_endpoint() -> None:
    source = MAIN_CPP.read_text(encoding="utf-8")
    header = (PROJECT_ROOT / "src" / "cpp" / "matter_bridge" / "BridgeDevice.h").read_text(
        encoding="utf-8"
    )
    impl = (PROJECT_ROOT / "src" / "cpp" / "matter_bridge" / "BridgeDevice.cpp").read_text(
        encoding="utf-8"
    )

    assert "GetUniqueId()" in header
    assert "unique_id_(info.device_id)" in impl
    assert "Attributes::UniqueID::Id" in impl
    assert "ZCL_UNIQUE_ID_ATTRIBUTE_ID" in impl
    assert "Attributes::UniqueID::Id" in source
    assert "dev->GetUniqueId()" in source
