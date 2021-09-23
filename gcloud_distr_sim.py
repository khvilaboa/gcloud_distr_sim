
from collections import Counter
import re
import subprocess
import time

from lxml import etree
import os
import sys
import time


class YAMLGenerator:
    CMD_GET_NODES = "kubectl get nodes --no-headers | cut -f1 -d' '"

    POD_TEMPLATE = """
---
apiVersion: v1
kind: Pod
metadata:
  name: {name}
  labels:
    app: distributed-devstone
spec:
  nodeName: {node}
  containers:
{containers}"""

    CONTAINER_TEMPLATE = """    - name: {name}
      image: {image}
      command: ["/bin/sleep"]
      args: ["infinity"]
      ports:
{ports}"""

    PORT_TEMPLATE = """        - name: {name}
          containerPort: {port}
          protocol: TCP"""

    def __init__(self, in_xml, image="debian:buster"):
        self.in_xml = in_xml
        self.image = image
        self.pods = {}

    def generate_yaml(self, out_yaml=None):
        if out_yaml is None:
            out_yaml = os.path.splitext(self.in_xml)[0] + ".yaml"
        coupled = etree.parse(open(self.in_xml, "r")).getroot()
        gen = None

        for child in coupled:
            if child.tag == "atomic":
                if child.attrib["name"].lower() == "generator":
                    gen = child
                else:
                    self._add_child_info(child)

        spods = list(sorted(self.pods))
        if gen is not None:
            self._add_child_info(gen, force_pod=spods[0])

        nodes_gen = YAMLGenerator._node_generator()

        with open(out_yaml, "w") as out_yaml_f:
            for pod_name in spods:
                ports_yaml = []

                if pod_name == spods[0]:  # Adds coord ports
                    main_port, aux_port = coupled.attrib["mainPort"], coupled.attrib["auxPort"]
                    self._add_port_yaml(ports_yaml, "coupled", main_port, aux_port)

                for atomic_name in sorted(self.pods[pod_name]):
                    main_port, aux_port, args = self.pods[pod_name][atomic_name]
                    atomic_name = atomic_name.lower().replace("_", "-")
                    self._add_port_yaml(ports_yaml, atomic_name, main_port, aux_port)

                container_yaml = YAMLGenerator.CONTAINER_TEMPLATE.format(name=pod_name + "-container",
                                                                         image=self.image,
                                                                         ports="\n".join(ports_yaml))

                pod_yaml = YAMLGenerator.POD_TEMPLATE.format(name=pod_name, containers=container_yaml, node=next(nodes_gen))
                out_yaml_f.write(pod_yaml)

        return out_yaml

    def _add_port_yaml(self, yaml_list, name, main_port, aux_port):
        # Main port
        port_yaml = YAMLGenerator.PORT_TEMPLATE.format(name="%s-main" % name,
                                                       port=main_port)
        yaml_list.append(port_yaml)

        # Auxliary port
        port_yaml = YAMLGenerator.PORT_TEMPLATE.format(name="%s-aux" % name,
                                                       port=aux_port)
        yaml_list.append(port_yaml)

    def _add_child_info(self, child, force_pod=None):
        args = self._get_args(child)
        # print("Atomic:", args)
        name = child.attrib["name"]

        if force_pod is None:
            host = child.attrib["host"].lower()
            if host.endswith("-service"):
                host = host[:-8]
        else:
            host = force_pod

        info = (child.attrib["mainPort"], child.attrib["auxPort"], args)

        if host not in self.pods:
            self.pods[host] = {name: info}
        else:
            self.pods[host][name] = info

    def _get_args(self, elem):
        args = []
        for child in elem:
            if child.tag == "constructor-arg":
                args.append(child.attrib["value"])
        return args

    @staticmethod
    def _node_generator():
        nodes = subprocess.getoutput(YAMLGenerator.CMD_GET_NODES).split()
        i = 0

        while True:
            yield nodes[i]
            i = 0 if i == len(nodes) - 1 else (i + 1)


if __name__ == '__main__':
    # CMD_GET_FIRST_NODE_NAME = "kubectl get nodes -n default --no-headers=true | head -1 | cut -f1 -d ' '"
    # CMD_GET_NODE_IP_RANGE = "kubectl describe node {name} | grep PodCIDR: |  tr -s ' ' | cut -f2 -d ' '"
    # CMD_DELETE_VOLUME = "kubectl delete persistentvolume {name}"
    # CMD_DELETE_VOLUME_CLAIM = "kubectl delete persistentvolumeclaim {name}"
    FILE_XDEVS_JAR = "xdevs-1.1.0-jar-with-dependencies.jar"
    FILE_LAUNCH_ATOMICS = "launch_atomics.sh"
    CLASS_LAUNCH_NODE = "xdevs.core.examples.distributed.gpt.Node"

    CMD_APPLY_YAML = "kubectl apply -f {filename}"
    CMD_DELETE_PODS = "kubectl delete pods -l app=distributed-devstone" #  --force
    CMD_COPY_TO_PODS = "xargs -n 1 -P {num_threads} -I % kubectl cp {local_file_path} %:{remote_file_path}"
    CMD_COPY_TO_POD = "kubectl cp {local_file_path} {pod}:{remote_file_path}"
    # CMD_SHOW_PODS_NODES = "kubectl get pods -o wide --no-headers | tr -s ' ' | cut -f 7 -d ' ' | uniq -c"
    # CMD_SHOW_PODS_NODES_NUMS = CMD_SHOW_PODS_NODES + " | tr -s ' ' | cut -f 2 -d ' '"
    CMD_SHOW_PODS_NODES = "kubectl get pods -o wide --no-headers | tr -s ' ' | cut -f 7 -d ' '"

    # CMD_APT_UPDATE = "xargs -n 1 -P {num_threads} -I % kubectl exec % -- apt update"
    # CMD_APT_INSTALL_DEPENDENCIES = "xargs -n 1 -P {num_threads} -I % kubectl exec % -- apt install -y procps openjdk-11-jre"

    CMD_LAUNCH_COORDINATOR = "kubectl exec {pod} -- bash -c 'java -cp {jar} {cp} {xml_file}'"
    CMD_LAUNCH_NODE = "java -cp {jar} {cp} {xml_file} {atomic_name} > {atomic_name}.out 2> {atomic_name}.err &"
    CMD_LAUNCH_ATOMICS = "kubectl exec {pod} -- bash -c '/launch_atomics.sh > /dev/null 2> /dev/null'"
    CMD_EXEC_PERM = "kubectl exec {pod} -- chmod +x {filename}"
    CMD_MISC_CMD_PREF = "kubectl exec {pod} -- bash -c \"{cmd}\""

    CMD_GET_PODS_IPS = "kubectl get pods -n default -o wide --no-headers=true -l app=distributed-devstone | awk '{{print $6; print $1}}'"

    # print("Determining cluster ip range...")
    # node_name = subprocess.getoutput(CMD_GET_FIRST_NODE_NAME)
    # ip_range = subprocess.getoutput(CMD_GET_NODE_IP_RANGE.format(name=node_name))
    # print("IP range: %s" % ip_range)

    def exec_cmd_all_pods(cmd, print_resp=True):
        prev = "kubectl get pods -n default --no-headers=true -l app=distributed-devstone | cut -f 1 -d ' ' | "
        cmd = prev + cmd
        resp = subprocess.getoutput(cmd)
        if print_resp:
            print(resp)


    def upload_to_pods(local_file_path, remote_file_path=None, num_threads=10, single_pod=None):
        if remote_file_path is None:
            remote_file_path = "/"
        remote_file_path = os.path.join(remote_file_path, os.path.basename(local_file_path))

        if single_pod is None:
            print(remote_file_path)
            exec_cmd_all_pods(CMD_COPY_TO_PODS.format(local_file_path=local_file_path,
                                                      remote_file_path=remote_file_path,
                                                      num_threads=num_threads), print_resp=False)
        else:
            cmd = CMD_COPY_TO_POD.format(local_file_path=local_file_path,
                                         remote_file_path=remote_file_path,
                                         pod=single_pod)
            subprocess.getoutput(cmd)


    def get_pod_hosts(nodes, pod):
        return ";".join(["echo %s>>/etc/hosts" % "    ".join(n) for n in nodes if n[1] != pod])

    fn = sys.argv[1]
    start_time = time.time()

    print("\nGenerating YAML file...")
    # The image "khenares/distributed-devstone-xdevs-java" is based on debian:buster, but has procps and
    # openjdk-11-jre installed (used to speed up deployment time).
    yaml_gen = YAMLGenerator(fn, image="khenares/distributed-devstone-xdevs-java")
    out_yaml_fn = yaml_gen.generate_yaml()
    print("%s generated successfully." % out_yaml_fn)

    print("\nDeploying resources...")
    exec_cmd_all_pods(CMD_APPLY_YAML.format(filename=out_yaml_fn))
    print("Pods assigment:")
    #print(subprocess.getoutput(CMD_SHOW_PODS_NODES))
    pods_per_node = Counter(subprocess.getoutput(CMD_SHOW_PODS_NODES).split())
    for node, num_pods in pods_per_node.items():
        print("%s: %d" % (node, num_pods))

    print("\nUploading shared files...")
    upload_to_pods(FILE_XDEVS_JAR)
    upload_to_pods(fn)

    # print("\nUpdating repositories...")
    # exec_cmd_all_pods(CMD_APT_UPDATE.format(num_threads=50), print_resp=False)
    # print("Installing dependencies...")
    # exec_cmd_all_pods(CMD_APT_INSTALL_DEPENDENCIES.format(num_threads=25), print_resp=False)

    node_ips = subprocess.getoutput(CMD_GET_PODS_IPS).split()
    node_ips = list(zip(node_ips[::2], node_ips[1::2]))

    print("\nDeploying atomic nodes:")
    for pod_name in sorted(yaml_gen.pods):
        with open(FILE_LAUNCH_ATOMICS, "w") as out:
            for atomic_name in yaml_gen.pods[pod_name]:
                # print(pod_name, atomic_name)
                cmd = CMD_LAUNCH_NODE.format(jar=FILE_XDEVS_JAR,
                                             cp=CLASS_LAUNCH_NODE,
                                             xml_file=os.path.basename(fn),
                                             atomic_name=atomic_name)
                out.write(cmd + "\n")

        print("Launching atomics on %s pod..." % pod_name)
        #print("Uploading %s to %s..." % (FILE_LAUNCH_ATOMICS, pod_name))
        upload_to_pods(FILE_LAUNCH_ATOMICS, single_pod=pod_name)
        subprocess.getoutput(CMD_EXEC_PERM.format(pod=pod_name, filename=FILE_LAUNCH_ATOMICS))
        subprocess.getoutput(CMD_LAUNCH_ATOMICS.format(pod=pod_name))
        # print(CMD_MISC_CMD_PREF.format(pod=pod_name, cmd=get_pod_hosts(node_ips, pod_name)))
        subprocess.getoutput(CMD_MISC_CMD_PREF.format(pod=pod_name, cmd=get_pod_hosts(node_ips, pod_name)))

    os.remove(FILE_LAUNCH_ATOMICS)

    deployment_time = time.time() - start_time

    # Atomics launch is executed as background processes, this is a delay to ensure initialization completion
    # They may appear some "Connection refused" errors when initializing if this time is too low, probably on
    # the last deployed pods (the suitable time depends on the amount of atomics/pods)
    waiting_sec = max(800, int(3.5*len(yaml_gen.pods)))
    print("\nWaiting for atomics to be completely deployed... (%d s)" % waiting_sec)
    time.sleep(waiting_sec)

    print("\nDeployment completed.")
    print("Time: %.2fs" % deployment_time)

    coordinator_pod = list(sorted(yaml_gen.pods))[0]
    print("\nLaunching simulation coordinator in %s..." % coordinator_pod)
    print(CMD_LAUNCH_COORDINATOR.format(pod=coordinator_pod, jar=FILE_XDEVS_JAR, cp=CLASS_LAUNCH_NODE, xml_file=os.path.basename(fn)))
    t_before_launch = time.time()
    sim_out = subprocess.getoutput(
        CMD_LAUNCH_COORDINATOR.format(pod=coordinator_pod, jar=FILE_XDEVS_JAR, cp=CLASS_LAUNCH_NODE, xml_file=os.path.basename(fn)))
    #CMD_LAUNCH_COORDINATOR = "kubectl exec {pod} -- bash -c 'java -cp {jar} {cp} {xml_file}'"

    try:
        print("SIMOUT: ", sim_out)
        sim_time = re.search("TIME: ([0-9.]+)", sim_out).group(1)
    except AttributeError:
        print("Error extracting simulation time (after %.2fs of simulation)" % (time.time()-t_before_launch))
        print("Simulation output: ", sim_out)
        raise RuntimeError("Simulation error.")

    print("Simulation completed! :)")
    print("Time: %ss" % sim_time)

    sim_times_file_exists = os.path.exists("sim_times.csv")
    with open("sim_times.csv", "a") as out:
        if not sim_times_file_exists:
            out.write("filename;deployment_time;sim_time;pods_per_node\n")

        out.write(";".join((fn, str(deployment_time), sim_time, "-".join(map(str, pods_per_node.values())))) + "\n")

    print("\nReleasing resources...")
    print(subprocess.getoutput(CMD_DELETE_PODS))
