"""Intensive unit tests for ManifestGenerator.

Covers all resource types, edge cases, validation errors, and structural
correctness of generated manifests.
"""

import pytest
from deploymind.infrastructure.cloud.kubernetes.manifest_generator import ManifestGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gen():
    return ManifestGenerator()


# ---------------------------------------------------------------------------
# Deployment tests
# ---------------------------------------------------------------------------

class TestGenerateDeployment:
    def test_minimal_deployment(self, gen):
        m = gen.generate_deployment(name="myapp", image="myapp:latest")
        assert m["apiVersion"] == "apps/v1"
        assert m["kind"] == "Deployment"
        assert m["metadata"]["name"] == "myapp"
        assert m["spec"]["replicas"] == 2

    def test_deployment_labels(self, gen):
        m = gen.generate_deployment("app", "img:1")
        assert m["metadata"]["labels"]["managed-by"] == "deploymind"
        assert m["spec"]["selector"]["matchLabels"]["app"] == "app"

    def test_deployment_container_port(self, gen):
        m = gen.generate_deployment("app", "img:1", port=9090)
        container = m["spec"]["template"]["spec"]["containers"][0]
        assert container["ports"][0]["containerPort"] == 9090

    def test_deployment_env_vars(self, gen):
        m = gen.generate_deployment("app", "img:1", env_vars={"FOO": "bar", "NUM": "42"})
        env = m["spec"]["template"]["spec"]["containers"][0]["env"]
        env_dict = {e["name"]: e["value"] for e in env}
        assert env_dict["FOO"] == "bar"
        assert env_dict["NUM"] == "42"

    def test_deployment_no_env_vars(self, gen):
        m = gen.generate_deployment("app", "img:1")
        env = m["spec"]["template"]["spec"]["containers"][0]["env"]
        assert env == []

    def test_deployment_resource_limits(self, gen):
        m = gen.generate_deployment("app", "img:1", cpu_request="200m", memory_limit="1Gi")
        resources = m["spec"]["template"]["spec"]["containers"][0]["resources"]
        assert resources["requests"]["cpu"] == "200m"
        assert resources["limits"]["memory"] == "1Gi"

    def test_deployment_health_probes(self, gen):
        m = gen.generate_deployment("app", "img:1", health_check_path="/ping", port=3000)
        container = m["spec"]["template"]["spec"]["containers"][0]
        assert container["livenessProbe"]["httpGet"]["path"] == "/ping"
        assert container["livenessProbe"]["httpGet"]["port"] == 3000
        assert container["readinessProbe"]["httpGet"]["path"] == "/ping"

    def test_deployment_rolling_update_strategy(self, gen):
        m = gen.generate_deployment("app", "img:1")
        strategy = m["spec"]["strategy"]
        assert strategy["type"] == "RollingUpdate"
        assert strategy["rollingUpdate"]["maxUnavailable"] == 0

    def test_deployment_custom_replicas(self, gen):
        m = gen.generate_deployment("app", "img:1", replicas=5)
        assert m["spec"]["replicas"] == 5

    def test_deployment_namespace(self, gen):
        m = gen.generate_deployment("app", "img:1", namespace="staging")
        assert m["metadata"]["namespace"] == "staging"

    def test_deployment_custom_labels(self, gen):
        m = gen.generate_deployment("app", "img:1", labels={"env": "prod", "team": "backend"})
        pod_labels = m["spec"]["template"]["metadata"]["labels"]
        assert pod_labels["env"] == "prod"
        assert pod_labels["team"] == "backend"

    def test_deployment_annotations(self, gen):
        m = gen.generate_deployment("app", "img:1", annotations={"note": "test"})
        assert m["metadata"]["annotations"]["note"] == "test"

    def test_deployment_image_pull_policy(self, gen):
        m = gen.generate_deployment("app", "img:1", image_pull_policy="Always")
        container = m["spec"]["template"]["spec"]["containers"][0]
        assert container["imagePullPolicy"] == "Always"

    def test_deployment_termination_grace_period(self, gen):
        m = gen.generate_deployment("app", "img:1")
        spec = m["spec"]["template"]["spec"]
        assert spec["terminationGracePeriodSeconds"] == 30

    def test_deployment_raises_empty_name(self, gen):
        with pytest.raises(ValueError, match="name must not be empty"):
            gen.generate_deployment("", "img:1")

    def test_deployment_raises_empty_image(self, gen):
        with pytest.raises(ValueError, match="image must not be empty"):
            gen.generate_deployment("app", "")

    def test_deployment_raises_zero_replicas(self, gen):
        with pytest.raises(ValueError, match="replicas must be >= 1"):
            gen.generate_deployment("app", "img:1", replicas=0)

    def test_deployment_raises_negative_replicas(self, gen):
        with pytest.raises(ValueError, match="replicas must be >= 1"):
            gen.generate_deployment("app", "img:1", replicas=-1)

    def test_deployment_raises_bad_health_path(self, gen):
        with pytest.raises(ValueError, match="health_check_path must start with"):
            gen.generate_deployment("app", "img:1", health_check_path="health")

    def test_deployment_raises_invalid_name_chars(self, gen):
        with pytest.raises(ValueError, match="invalid characters"):
            gen.generate_deployment("my app!", "img:1")

    def test_deployment_name_with_hyphen_allowed(self, gen):
        m = gen.generate_deployment("my-app", "img:1")
        assert m["metadata"]["name"] == "my-app"

    def test_deployment_name_with_dot_allowed(self, gen):
        m = gen.generate_deployment("my.app", "img:1")
        assert m["metadata"]["name"] == "my.app"


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------

class TestGenerateService:
    def test_minimal_service(self, gen):
        m = gen.generate_service("myapp", port=8080)
        assert m["kind"] == "Service"
        assert m["spec"]["type"] == "ClusterIP"
        assert m["spec"]["ports"][0]["port"] == 8080

    def test_service_target_port_defaults_to_port(self, gen):
        m = gen.generate_service("app", port=8080)
        assert m["spec"]["ports"][0]["targetPort"] == 8080

    def test_service_custom_target_port(self, gen):
        m = gen.generate_service("app", port=80, target_port=8080)
        assert m["spec"]["ports"][0]["port"] == 80
        assert m["spec"]["ports"][0]["targetPort"] == 8080

    def test_service_node_port_type(self, gen):
        m = gen.generate_service("app", port=80, service_type="NodePort", node_port=30080)
        assert m["spec"]["type"] == "NodePort"
        assert m["spec"]["ports"][0]["nodePort"] == 30080

    def test_service_load_balancer_type(self, gen):
        m = gen.generate_service("app", port=80, service_type="LoadBalancer")
        assert m["spec"]["type"] == "LoadBalancer"

    def test_service_selector_defaults_to_app_label(self, gen):
        m = gen.generate_service("myapp", port=80)
        assert m["spec"]["selector"]["app"] == "myapp"

    def test_service_custom_selector(self, gen):
        m = gen.generate_service("svc", port=80, selector_labels={"app": "myapp", "color": "blue"})
        assert m["spec"]["selector"]["color"] == "blue"

    def test_service_namespace(self, gen):
        m = gen.generate_service("app", port=80, namespace="prod")
        assert m["metadata"]["namespace"] == "prod"

    def test_service_raises_invalid_type(self, gen):
        with pytest.raises(ValueError, match="service_type must be one of"):
            gen.generate_service("app", port=80, service_type="Invalid")

    def test_service_raises_node_port_out_of_range_low(self, gen):
        with pytest.raises(ValueError, match="node_port must be 30000-32767"):
            gen.generate_service("app", port=80, service_type="NodePort", node_port=1000)

    def test_service_raises_node_port_out_of_range_high(self, gen):
        with pytest.raises(ValueError, match="node_port must be 30000-32767"):
            gen.generate_service("app", port=80, service_type="NodePort", node_port=40000)

    def test_service_node_port_boundary_low(self, gen):
        m = gen.generate_service("app", port=80, service_type="NodePort", node_port=30000)
        assert m["spec"]["ports"][0]["nodePort"] == 30000

    def test_service_node_port_boundary_high(self, gen):
        m = gen.generate_service("app", port=80, service_type="NodePort", node_port=32767)
        assert m["spec"]["ports"][0]["nodePort"] == 32767

    def test_service_labels(self, gen):
        m = gen.generate_service("app", port=80)
        assert m["metadata"]["labels"]["managed-by"] == "deploymind"


# ---------------------------------------------------------------------------
# Ingress tests
# ---------------------------------------------------------------------------

class TestGenerateIngress:
    def test_minimal_ingress(self, gen):
        m = gen.generate_ingress("myapp", host="myapp.example.com", service_name="myapp", port=8080)
        assert m["kind"] == "Ingress"
        assert m["spec"]["rules"][0]["host"] == "myapp.example.com"

    def test_ingress_backend_service(self, gen):
        m = gen.generate_ingress("myapp", host="x.com", service_name="mysvc", port=80)
        backend = m["spec"]["rules"][0]["http"]["paths"][0]["backend"]
        assert backend["service"]["name"] == "mysvc"
        assert backend["service"]["port"]["number"] == 80

    def test_ingress_tls(self, gen):
        m = gen.generate_ingress(
            "app", host="app.example.com", service_name="app", port=80,
            tls_secret="app-tls"
        )
        assert m["spec"]["tls"][0]["secretName"] == "app-tls"
        assert "app.example.com" in m["spec"]["tls"][0]["hosts"]

    def test_ingress_no_tls_by_default(self, gen):
        m = gen.generate_ingress("app", host="app.com", service_name="app", port=80)
        assert "tls" not in m["spec"]

    def test_ingress_custom_annotations(self, gen):
        m = gen.generate_ingress(
            "app", host="app.com", service_name="app", port=80,
            annotations={"nginx.ingress.kubernetes.io/rewrite-target": "/"}
        )
        assert "nginx.ingress.kubernetes.io/rewrite-target" in m["metadata"]["annotations"]

    def test_ingress_custom_path(self, gen):
        m = gen.generate_ingress("app", host="app.com", service_name="app", port=80, path="/api")
        path_entry = m["spec"]["rules"][0]["http"]["paths"][0]
        assert path_entry["path"] == "/api"

    def test_ingress_path_type_prefix(self, gen):
        m = gen.generate_ingress("app", host="app.com", service_name="app", port=80)
        assert m["spec"]["rules"][0]["http"]["paths"][0]["pathType"] == "Prefix"

    def test_ingress_ingress_class_name(self, gen):
        m = gen.generate_ingress(
            "app", host="app.com", service_name="app", port=80, ingress_class="traefik"
        )
        assert m["spec"]["ingressClassName"] == "traefik"

    def test_ingress_raises_empty_host(self, gen):
        with pytest.raises(ValueError, match="host must not be empty"):
            gen.generate_ingress("app", host="", service_name="app", port=80)

    def test_ingress_raises_bad_path(self, gen):
        with pytest.raises(ValueError, match="path must start with"):
            gen.generate_ingress("app", host="app.com", service_name="app", port=80, path="api")

    def test_ingress_namespace(self, gen):
        m = gen.generate_ingress(
            "app", host="app.com", service_name="app", port=80, namespace="staging"
        )
        assert m["metadata"]["namespace"] == "staging"


# ---------------------------------------------------------------------------
# HPA tests
# ---------------------------------------------------------------------------

class TestGenerateHPA:
    def test_minimal_hpa(self, gen):
        m = gen.generate_hpa("myapp")
        assert m["kind"] == "HorizontalPodAutoscaler"
        assert m["metadata"]["name"] == "myapp-hpa"

    def test_hpa_scale_target(self, gen):
        m = gen.generate_hpa("myapp")
        target = m["spec"]["scaleTargetRef"]
        assert target["kind"] == "Deployment"
        assert target["name"] == "myapp"

    def test_hpa_defaults(self, gen):
        m = gen.generate_hpa("app")
        assert m["spec"]["minReplicas"] == 1
        assert m["spec"]["maxReplicas"] == 10

    def test_hpa_custom_replicas(self, gen):
        m = gen.generate_hpa("app", min_replicas=2, max_replicas=20)
        assert m["spec"]["minReplicas"] == 2
        assert m["spec"]["maxReplicas"] == 20

    def test_hpa_cpu_target(self, gen):
        m = gen.generate_hpa("app", cpu_target_percent=80)
        metric = m["spec"]["metrics"][0]
        assert metric["resource"]["target"]["averageUtilization"] == 80

    def test_hpa_namespace(self, gen):
        m = gen.generate_hpa("app", namespace="prod")
        assert m["metadata"]["namespace"] == "prod"

    def test_hpa_raises_zero_min(self, gen):
        with pytest.raises(ValueError, match="min_replicas must be >= 1"):
            gen.generate_hpa("app", min_replicas=0)

    def test_hpa_raises_max_less_than_min(self, gen):
        with pytest.raises(ValueError, match="max_replicas.*must be >= min_replicas"):
            gen.generate_hpa("app", min_replicas=5, max_replicas=3)

    def test_hpa_raises_invalid_cpu_percent_zero(self, gen):
        with pytest.raises(ValueError, match="cpu_target_percent must be 1-100"):
            gen.generate_hpa("app", cpu_target_percent=0)

    def test_hpa_raises_invalid_cpu_percent_over_100(self, gen):
        with pytest.raises(ValueError, match="cpu_target_percent must be 1-100"):
            gen.generate_hpa("app", cpu_target_percent=101)

    def test_hpa_cpu_percent_boundary_1(self, gen):
        m = gen.generate_hpa("app", cpu_target_percent=1)
        assert m["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"] == 1

    def test_hpa_cpu_percent_boundary_100(self, gen):
        m = gen.generate_hpa("app", cpu_target_percent=100)
        assert m["spec"]["metrics"][0]["resource"]["target"]["averageUtilization"] == 100


# ---------------------------------------------------------------------------
# Canary manifests tests
# ---------------------------------------------------------------------------

class TestGenerateCanaryManifests:
    def test_canary_returns_keys(self, gen):
        result = gen.generate_canary_manifests(
            name="myapp",
            stable_image="myapp:v1",
            canary_image="myapp:v2",
        )
        assert "stable" in result
        assert "canary" in result
        assert "service" in result

    def test_canary_stable_name(self, gen):
        result = gen.generate_canary_manifests("app", "app:v1", "app:v2")
        assert result["stable"][0]["metadata"]["name"] == "app-stable"

    def test_canary_canary_name(self, gen):
        result = gen.generate_canary_manifests("app", "app:v1", "app:v2")
        assert result["canary"][0]["metadata"]["name"] == "app-canary"

    def test_canary_stable_image(self, gen):
        result = gen.generate_canary_manifests("app", "app:v1", "app:v2")
        container = result["stable"][0]["spec"]["template"]["spec"]["containers"][0]
        assert container["image"] == "app:v1"

    def test_canary_canary_image(self, gen):
        result = gen.generate_canary_manifests("app", "app:v1", "app:v2")
        container = result["canary"][0]["spec"]["template"]["spec"]["containers"][0]
        assert container["image"] == "app:v2"

    def test_canary_replica_counts(self, gen):
        result = gen.generate_canary_manifests("app", "app:v1", "app:v2",
                                               stable_replicas=9, canary_replicas=1)
        assert result["stable"][0]["spec"]["replicas"] == 9
        assert result["canary"][0]["spec"]["replicas"] == 1

    def test_canary_service_shared_selector(self, gen):
        result = gen.generate_canary_manifests("app", "app:v1", "app:v2")
        svc_selector = result["service"][0]["spec"]["selector"]
        assert svc_selector["app"] == "app"
        # Selector must NOT have "track" — routes to both stable and canary pods
        assert "track" not in svc_selector

    def test_canary_track_labels(self, gen):
        result = gen.generate_canary_manifests("app", "app:v1", "app:v2")
        stable_labels = result["stable"][0]["spec"]["template"]["metadata"]["labels"]
        canary_labels = result["canary"][0]["spec"]["template"]["metadata"]["labels"]
        assert stable_labels["track"] == "stable"
        assert canary_labels["track"] == "canary"

    def test_canary_weight_annotation_10pct(self, gen):
        result = gen.generate_canary_manifests("app", "app:v1", "app:v2",
                                               stable_replicas=9, canary_replicas=1)
        annotation = result["canary"][0]["metadata"]["annotations"]["deploymind.io/canary-weight"]
        assert annotation == "10"

    def test_canary_weight_annotation_50pct(self, gen):
        result = gen.generate_canary_manifests("app", "app:v1", "app:v2",
                                               stable_replicas=1, canary_replicas=1)
        annotation = result["canary"][0]["metadata"]["annotations"]["deploymind.io/canary-weight"]
        assert annotation == "50"

    def test_canary_raises_zero_stable_replicas(self, gen):
        with pytest.raises(ValueError, match="stable_replicas and canary_replicas must each be >= 1"):
            gen.generate_canary_manifests("app", "app:v1", "app:v2", stable_replicas=0)

    def test_canary_raises_zero_canary_replicas(self, gen):
        with pytest.raises(ValueError, match="stable_replicas and canary_replicas must each be >= 1"):
            gen.generate_canary_manifests("app", "app:v1", "app:v2", canary_replicas=0)


# ---------------------------------------------------------------------------
# Blue-Green manifests tests
# ---------------------------------------------------------------------------

class TestGenerateBlueGreenManifests:
    def test_blue_green_returns_keys(self, gen):
        result = gen.generate_blue_green_manifests("app", "app:blue", "app:green")
        assert "blue" in result
        assert "green" in result
        assert "service" in result

    def test_blue_green_blue_name(self, gen):
        result = gen.generate_blue_green_manifests("app", "app:blue", "app:green")
        assert result["blue"]["metadata"]["name"] == "app-blue"

    def test_blue_green_green_name(self, gen):
        result = gen.generate_blue_green_manifests("app", "app:blue", "app:green")
        assert result["green"]["metadata"]["name"] == "app-green"

    def test_blue_green_active_color_blue_service_selector(self, gen):
        result = gen.generate_blue_green_manifests("app", "app:v1", "app:v2", active_color="blue")
        selector = result["service"]["spec"]["selector"]
        assert selector["color"] == "blue"

    def test_blue_green_active_color_green_service_selector(self, gen):
        result = gen.generate_blue_green_manifests("app", "app:v1", "app:v2", active_color="green")
        selector = result["service"]["spec"]["selector"]
        assert selector["color"] == "green"

    def test_blue_green_color_labels_on_pods(self, gen):
        result = gen.generate_blue_green_manifests("app", "app:v1", "app:v2", active_color="blue")
        blue_labels = result["blue"]["spec"]["template"]["metadata"]["labels"]
        green_labels = result["green"]["spec"]["template"]["metadata"]["labels"]
        assert blue_labels["color"] == "blue"
        assert green_labels["color"] == "green"

    def test_blue_green_replicas(self, gen):
        result = gen.generate_blue_green_manifests("app", "app:v1", "app:v2", replicas=4)
        assert result["blue"]["spec"]["replicas"] == 4
        assert result["green"]["spec"]["replicas"] == 4

    def test_blue_green_raises_invalid_color(self, gen):
        with pytest.raises(ValueError, match="active_color must be 'blue' or 'green'"):
            gen.generate_blue_green_manifests("app", "img:1", "img:2", active_color="red")

    def test_promote_blue_green_blue_to_green(self, gen):
        m = gen.promote_blue_green("app", current_color="blue")
        assert m["spec"]["selector"]["color"] == "green"

    def test_promote_blue_green_green_to_blue(self, gen):
        m = gen.promote_blue_green("app", current_color="green")
        assert m["spec"]["selector"]["color"] == "blue"

    def test_promote_raises_invalid_color(self, gen):
        with pytest.raises(ValueError, match="current_color must be 'blue' or 'green'"):
            gen.promote_blue_green("app", current_color="red")
