from architecture_model.java_runtime_adapter import (
    _parse_jfr_json,
    discover_spring_boot_entrypoint,
)


def test_discovers_spring_boot_main_not_configuration_class(tmp_path):
    app = tmp_path / "src/main/java/com/example/DemoApplication.java"
    config = tmp_path / "src/main/java/com/example/HibernateConfiguration.java"
    app.parent.mkdir(parents=True)
    app.write_text(
        "package com.example;\n@SpringBootApplication\n"
        "public class DemoApplication { public static void main(String[] args) {} }",
        encoding="utf-8",
    )
    config.write_text(
        "package com.example;\n@Configuration\n"
        "public class HibernateConfiguration {}",
        encoding="utf-8",
    )
    assert discover_spring_boot_entrypoint(tmp_path) == (
        "src/main/java/com/example/DemoApplication.java"
    )


def test_jfr_parser_extracts_only_project_package_edges(tmp_path):
    source = tmp_path / "src/main/java/com/example/App.java"
    source.parent.mkdir(parents=True)
    source.write_text("package com.example; public class App {}", encoding="utf-8")
    payload = {
        "recording": {
            "events": [{
                "type": "jdk.ExecutionSample",
                "values": {
                    "stackTrace": {
                        "frames": [
                            {"method": {"type": {"name": "com.example.Service"}, "name": "load"}},
                            {"method": {"type": {"name": "com.example.Controller"}, "name": "handle"}},
                            {"method": {"type": {"name": "org.springframework.Dispatcher"}, "name": "dispatch"}},
                        ]
                    }
                }
            }]
        }
    }
    edges = _parse_jfr_json(payload, tmp_path)
    assert edges == [{
        "caller_module": "com.example.Controller",
        "caller_function": "handle",
        "callee_module": "com.example.Service",
        "callee_function": "load",
        "samples": 1,
    }]
