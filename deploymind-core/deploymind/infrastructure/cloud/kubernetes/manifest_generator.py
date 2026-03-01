"""Kubernetes manifest generator.

Produces ready-to-apply Python dicts (equivalent to YAML manifests) for
common Kubernetes resources used in DeployMind deployments.

All methods return plain ``dict`` objects that can be passed directly to
``KubernetesClient.deploy_to_kubernetes()`` or serialised with ``yaml.dump()``.

Supported resources:
  - Deployment (rolling, with configurable replicas, resources, probes)
  - Service (ClusterIP, NodePort, LoadBalancer)
  - Ingress (nginx or generic)
  - HorizontalPodAutoscaler
  - Canary Deployment pair (stable + canary with traffic weights)
  - Blue-Green Deployment pair (blue + green + active Service)
"""

from __future__ import annotations

from typing import Optional


class ManifestGenerator:
    """Generates Kubernetes resource manifests as Python dicts.

    Example::

        gen = ManifestGenerator()
        deployment = gen.generate_deployment(
            name="myapp",
            image="myrepo/myapp:abc1234",
            replicas=3,
            port=8080,
            namespace="production",
        )
        service = gen.generate_service("myapp", port=8080, namespace="production")
    """

    # Default resource requests/limits applied to every container
    _DEFAULT_REQUESTS = {"cpu": "100m", "memory": "128Mi"}
    _DEFAULT_LIMITS = {"cpu": "500m", "memory": "512Mi"}

    # ------------------------------------------------------------------
    # Deployment
    # ------------------------------------------------------------------

    def generate_deployment(
        self,
        name: str,
        image: str,
        replicas: int = 2,
        port: int = 8080,
        namespace: str = "default",
        env_vars: Optional[dict[str, str]] = None,
        health_check_path: str = "/health",
        cpu_request: str = "100m",
        cpu_limit: str = "500m",
        memory_request: str = "128Mi",
        memory_limit: str = "512Mi",
        labels: Optional[dict[str, str]] = None,
        annotations: Optional[dict[str, str]] = None,
        image_pull_policy: str = "IfNotPresent",
    ) -> dict:
        """Generate a Kubernetes Deployment manifest.

        Args:
            name: Name of the deployment (also used as ``app`` label).
            image: Full image reference including tag.
            replicas: Number of desired pod replicas.
            port: Container port to expose.
            namespace: Target namespace.
            env_vars: Optional environment variable dict ``{KEY: value}``.
            health_check_path: HTTP path for liveness/readiness probes.
            cpu_request: CPU request (e.g. ``"100m"``).
            cpu_limit: CPU limit (e.g. ``"500m"``).
            memory_request: Memory request (e.g. ``"128Mi"``).
            memory_limit: Memory limit (e.g. ``"512Mi"``).
            labels: Extra pod labels merged with ``app: <name>``.
            annotations: Optional deployment annotations.
            image_pull_policy: ``Always``, ``IfNotPresent``, or ``Never``.

        Returns:
            Deployment manifest dict.

        Raises:
            ValueError: If name or image is empty, or replicas < 1.
        """
        self._validate_name(name)
        self._validate_image(image)
        if replicas < 1:
            raise ValueError(f"replicas must be >= 1, got {replicas}")
        if not health_check_path.startswith("/"):
            raise ValueError(f"health_check_path must start with '/', got {health_check_path!r}")

        pod_labels = {"app": name, "version": "latest"}
        if labels:
            pod_labels.update(labels)

        container_env = []
        if env_vars:
            container_env = [
                {"name": k, "value": str(v)}
                for k, v in env_vars.items()
            ]

        manifest: dict = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": {"app": name, "managed-by": "deploymind"},
            },
            "spec": {
                "replicas": replicas,
                "selector": {"matchLabels": {"app": name}},
                "strategy": {
                    "type": "RollingUpdate",
                    "rollingUpdate": {"maxSurge": 1, "maxUnavailable": 0},
                },
                "template": {
                    "metadata": {"labels": pod_labels},
                    "spec": {
                        "containers": [
                            {
                                "name": name,
                                "image": image,
                                "imagePullPolicy": image_pull_policy,
                                "ports": [{"containerPort": port}],
                                "env": container_env,
                                "resources": {
                                    "requests": {"cpu": cpu_request, "memory": memory_request},
                                    "limits": {"cpu": cpu_limit, "memory": memory_limit},
                                },
                                "livenessProbe": {
                                    "httpGet": {"path": health_check_path, "port": port},
                                    "initialDelaySeconds": 15,
                                    "periodSeconds": 20,
                                    "failureThreshold": 3,
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": health_check_path, "port": port},
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 10,
                                    "failureThreshold": 3,
                                },
                            }
                        ],
                        "terminationGracePeriodSeconds": 30,
                    },
                },
            },
        }

        if annotations:
            manifest["metadata"]["annotations"] = annotations

        return manifest

    # ------------------------------------------------------------------
    # Service
    # ------------------------------------------------------------------

    def generate_service(
        self,
        name: str,
        port: int = 8080,
        namespace: str = "default",
        service_type: str = "ClusterIP",
        target_port: Optional[int] = None,
        node_port: Optional[int] = None,
        selector_labels: Optional[dict[str, str]] = None,
    ) -> dict:
        """Generate a Kubernetes Service manifest.

        Args:
            name: Service name (also used as the ``app`` selector).
            port: Port exposed by the service.
            namespace: Target namespace.
            service_type: ``"ClusterIP"``, ``"NodePort"``, or ``"LoadBalancer"``.
            target_port: Container port; defaults to ``port``.
            node_port: NodePort value (only when ``service_type="NodePort"``).
            selector_labels: Override pod selector; defaults to ``{"app": name}``.

        Returns:
            Service manifest dict.

        Raises:
            ValueError: If service_type is invalid or node_port out of range.
        """
        self._validate_name(name)
        valid_types = {"ClusterIP", "NodePort", "LoadBalancer"}
        if service_type not in valid_types:
            raise ValueError(f"service_type must be one of {valid_types}, got {service_type!r}")
        if node_port is not None and not (30000 <= node_port <= 32767):
            raise ValueError(f"node_port must be 30000-32767, got {node_port}")

        selector = selector_labels or {"app": name}
        port_spec: dict = {
            "protocol": "TCP",
            "port": port,
            "targetPort": target_port or port,
        }
        if service_type == "NodePort" and node_port is not None:
            port_spec["nodePort"] = node_port

        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": {"app": name, "managed-by": "deploymind"},
            },
            "spec": {
                "type": service_type,
                "selector": selector,
                "ports": [port_spec],
            },
        }

    # ------------------------------------------------------------------
    # Ingress
    # ------------------------------------------------------------------

    def generate_ingress(
        self,
        name: str,
        host: str,
        service_name: str,
        port: int,
        namespace: str = "default",
        path: str = "/",
        tls_secret: Optional[str] = None,
        ingress_class: str = "nginx",
        annotations: Optional[dict[str, str]] = None,
    ) -> dict:
        """Generate a Kubernetes Ingress manifest.

        Args:
            name: Ingress resource name.
            host: Fully-qualified hostname (e.g. ``"myapp.example.com"``).
            service_name: Backend Service name.
            port: Backend Service port.
            namespace: Target namespace.
            path: URL path prefix (default ``"/"``).
            tls_secret: Optional TLS secret name for HTTPS.
            ingress_class: Ingress class annotation (default ``"nginx"``).
            annotations: Additional annotations merged with the class annotation.

        Returns:
            Ingress manifest dict.

        Raises:
            ValueError: If host is empty or path does not start with '/'.
        """
        self._validate_name(name)
        if not host:
            raise ValueError("host must not be empty")
        if not path.startswith("/"):
            raise ValueError(f"path must start with '/', got {path!r}")

        base_annotations = {"kubernetes.io/ingress.class": ingress_class}
        if annotations:
            base_annotations.update(annotations)

        rule = {
            "host": host,
            "http": {
                "paths": [
                    {
                        "path": path,
                        "pathType": "Prefix",
                        "backend": {
                            "service": {
                                "name": service_name,
                                "port": {"number": port},
                            }
                        },
                    }
                ]
            },
        }

        manifest: dict = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "annotations": base_annotations,
                "labels": {"app": name, "managed-by": "deploymind"},
            },
            "spec": {
                "ingressClassName": ingress_class,
                "rules": [rule],
            },
        }

        if tls_secret:
            manifest["spec"]["tls"] = [{"hosts": [host], "secretName": tls_secret}]

        return manifest

    # ------------------------------------------------------------------
    # HorizontalPodAutoscaler
    # ------------------------------------------------------------------

    def generate_hpa(
        self,
        name: str,
        namespace: str = "default",
        min_replicas: int = 1,
        max_replicas: int = 10,
        cpu_target_percent: int = 70,
    ) -> dict:
        """Generate a HorizontalPodAutoscaler targeting a Deployment.

        Args:
            name: Deployment name to autoscale (HPA name = ``name + "-hpa"``).
            namespace: Target namespace.
            min_replicas: Minimum replica count.
            max_replicas: Maximum replica count.
            cpu_target_percent: Target CPU utilisation percentage.

        Returns:
            HPA manifest dict.

        Raises:
            ValueError: If min_replicas > max_replicas or percentages invalid.
        """
        self._validate_name(name)
        if min_replicas < 1:
            raise ValueError(f"min_replicas must be >= 1, got {min_replicas}")
        if max_replicas < min_replicas:
            raise ValueError(
                f"max_replicas ({max_replicas}) must be >= min_replicas ({min_replicas})"
            )
        if not (1 <= cpu_target_percent <= 100):
            raise ValueError(f"cpu_target_percent must be 1-100, got {cpu_target_percent}")

        return {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": f"{name}-hpa",
                "namespace": namespace,
                "labels": {"app": name, "managed-by": "deploymind"},
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": name,
                },
                "minReplicas": min_replicas,
                "maxReplicas": max_replicas,
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": cpu_target_percent,
                            },
                        },
                    }
                ],
            },
        }

    # ------------------------------------------------------------------
    # Canary strategy helpers
    # ------------------------------------------------------------------

    def generate_canary_manifests(
        self,
        name: str,
        stable_image: str,
        canary_image: str,
        stable_replicas: int = 9,
        canary_replicas: int = 1,
        port: int = 8080,
        namespace: str = "default",
        health_check_path: str = "/health",
    ) -> dict[str, list[dict]]:
        """Generate a canary deployment pair (stable + canary Deployments).

        Traffic is split proportionally based on replica counts.  For example,
        9 stable + 1 canary replica → 90% stable / 10% canary.

        Args:
            name: Base application name.
            stable_image: Existing stable image tag.
            canary_image: New canary image tag.
            stable_replicas: Stable replica count (controls traffic weight).
            canary_replicas: Canary replica count (controls traffic weight).
            port: Container port.
            namespace: Target namespace.
            health_check_path: Probe path.

        Returns:
            Dict with keys ``"stable"``, ``"canary"``, ``"service"`` each
            holding a list of manifest dicts to apply.

        Raises:
            ValueError: If replica counts are invalid.
        """
        self._validate_name(name)
        if stable_replicas < 1 or canary_replicas < 1:
            raise ValueError("stable_replicas and canary_replicas must each be >= 1")

        total = stable_replicas + canary_replicas
        canary_pct = round(canary_replicas / total * 100)

        stable_manifest = self.generate_deployment(
            name=f"{name}-stable",
            image=stable_image,
            replicas=stable_replicas,
            port=port,
            namespace=namespace,
            health_check_path=health_check_path,
            labels={"app": name, "track": "stable"},
        )
        canary_manifest = self.generate_deployment(
            name=f"{name}-canary",
            image=canary_image,
            replicas=canary_replicas,
            port=port,
            namespace=namespace,
            health_check_path=health_check_path,
            labels={"app": name, "track": "canary"},
            annotations={"deploymind.io/canary-weight": str(canary_pct)},
        )
        # Shared service routes to BOTH stable and canary pods (same app label)
        service_manifest = self.generate_service(
            name=name,
            port=port,
            namespace=namespace,
            selector_labels={"app": name},
        )

        return {
            "stable": [stable_manifest],
            "canary": [canary_manifest],
            "service": [service_manifest],
        }

    # ------------------------------------------------------------------
    # Blue-Green strategy helpers
    # ------------------------------------------------------------------

    def generate_blue_green_manifests(
        self,
        name: str,
        blue_image: str,
        green_image: str,
        active_color: str = "blue",
        replicas: int = 2,
        port: int = 8080,
        namespace: str = "default",
        health_check_path: str = "/health",
    ) -> dict[str, dict]:
        """Generate a blue-green deployment set.

        Two Deployments (blue + green) are maintained side-by-side.  The
        active Service selects one via the ``color`` label.  Promotion is
        achieved by patching ``spec.selector`` on the Service.

        Args:
            name: Base application name.
            blue_image: Image tag for the blue deployment.
            green_image: Image tag for the green deployment.
            active_color: Which color the Service currently points at.
            replicas: Replica count for each deployment.
            port: Container port.
            namespace: Target namespace.
            health_check_path: Probe path.

        Returns:
            Dict with keys ``"blue"``, ``"green"``, ``"service"`` each
            containing a single manifest dict.

        Raises:
            ValueError: If active_color is not ``"blue"`` or ``"green"``.
        """
        self._validate_name(name)
        if active_color not in ("blue", "green"):
            raise ValueError(f"active_color must be 'blue' or 'green', got {active_color!r}")

        blue_manifest = self.generate_deployment(
            name=f"{name}-blue",
            image=blue_image,
            replicas=replicas,
            port=port,
            namespace=namespace,
            health_check_path=health_check_path,
            labels={"app": name, "color": "blue"},
        )
        green_manifest = self.generate_deployment(
            name=f"{name}-green",
            image=green_image,
            replicas=replicas,
            port=port,
            namespace=namespace,
            health_check_path=health_check_path,
            labels={"app": name, "color": "green"},
        )
        # Service always routes to the active color
        service_manifest = self.generate_service(
            name=name,
            port=port,
            namespace=namespace,
            selector_labels={"app": name, "color": active_color},
        )

        return {
            "blue": blue_manifest,
            "green": green_manifest,
            "service": service_manifest,
        }

    def promote_blue_green(
        self,
        name: str,
        current_color: str,
        port: int = 8080,
        namespace: str = "default",
    ) -> dict:
        """Generate the Service patch to promote the inactive color.

        Args:
            name: Application name.
            current_color: The color currently active (``"blue"`` or ``"green"``).
            port: Service port.
            namespace: Namespace.

        Returns:
            Updated Service manifest pointing at the opposite color.
        """
        if current_color not in ("blue", "green"):
            raise ValueError(f"current_color must be 'blue' or 'green', got {current_color!r}")
        new_color = "green" if current_color == "blue" else "blue"
        return self.generate_service(
            name=name,
            port=port,
            namespace=namespace,
            selector_labels={"app": name, "color": new_color},
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_name(name: str) -> None:
        """Validate that a Kubernetes resource name is non-empty and DNS-safe."""
        if not name:
            raise ValueError("name must not be empty")
        if not all(c.isalnum() or c in "-." for c in name):
            raise ValueError(
                f"name {name!r} contains invalid characters. "
                "Use only alphanumeric characters, hyphens, and dots."
            )

    @staticmethod
    def _validate_image(image: str) -> None:
        """Validate that an image reference is non-empty."""
        if not image:
            raise ValueError("image must not be empty")
