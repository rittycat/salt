import docker
import re
import typer
import subprocess
import shlex
import time
from typing import Tuple

app = typer.Typer()


def add_rule(client: docker.client, name: str) -> bool:
    """
    Retrieve IPs for a container by name and add iptables rule for it
    :param client:
    :param name:
    :return:
    """
    try:
        container = client.containers.get(name)
        out_ip, in_ip = get_ips(container)

        comment = f"dfm_rule_{name}"
        command = (
            f"iptables -t nat -I POSTROUTING -p all -s {in_ip} -j SNAT --to-source {out_ip} "
            f"-m comment --comment {comment}"
        )

        subprocess.check_output(shlex.split(command))
    except docker.errors.NotFound:
        return False

    return True


def remove_rule(name: str) -> bool:
    """
    Removes iptables rule based on name
    :param name:
    :return:
    """
    try:
        rules = subprocess.check_output("iptables-save", encoding="UTF-8").splitlines()
        new_rules = []
        for rule in rules:
            if f"dfm_rule_{name}" in rule:
                continue
            new_rules.append(rule)

        rules_string = "\n".join(new_rules)

        pipe = subprocess.Popen("iptables-restore", stdin=subprocess.PIPE)
        pipe.communicate(input=rules_string.encode())
    except Exception:
        return False

    return True


def prune_rules(client: docker.client) -> bool:
    """
    Prune all rules for containers that are no longer running
    :param client:
    :return:
    """
    try:
        rules = subprocess.check_output("iptables-save", encoding="UTF-8").splitlines()
        running_names = [container.name for container in client.containers.list(ignore_removed=True)]

        new_rules = []
        for rule in rules:
            if "dfm_rule_" in rule:
                name = re.search("dfm_rule_(.*?) ", rule).group(1)
                if name not in running_names:
                    continue
            new_rules.append(rule)

        rules_string = "\n".join(new_rules)

        pipe = subprocess.Popen("iptables-restore", stdin=subprocess.PIPE)
        pipe.communicate(input=rules_string.encode())
    except Exception:
        return False

    return True


def get_ips(container: docker.models.containers.Container) -> Tuple[str, str]:
    """
    Returns internal and external IP for bridged container based off first port binding
    :param container:
    :return:
    """
    global _bridge

    network_settings = container.attrs["NetworkSettings"]
    _, port = network_settings["Ports"].popitem()

    external_ip = port[0]["HostIp"]
    internal_ip = network_settings["Networks"][_bridge]["IPAddress"]

    return external_ip, internal_ip


@app.command()
def main(bridge: str = typer.Argument(..., help="The name of the bridge network used by containers")):
    global _bridge
    _bridge = bridge

    client = docker.from_env()
    pattern = "^mc[0-9]+$"

    last_prune = time.time()
    for event in client.events(decode=True):
        name = event.get("Actor", {}).get("Attributes", {}).get("name", "")
        status = event.get("status", "")

        if re.match(pattern, name) and status == "start":
            add_rule(client, name)
            # Rate limit pruning
            check_time = time.time()
            if (check_time - last_prune) >= 1.5:
                last_prune = check_time
                prune_rules(client)
        elif status == "die":
            remove_rule(name)


_bridge = ""
if __name__ == "__main__":
    app()
