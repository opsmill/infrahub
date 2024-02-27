locals {
  infrahub_version = var.infrahub_version == "" ? "0.11" : var.infrahub_version
  vm_template_name = var.vm_template_name == "" ? "infrahub-${local.infrahub_version}-ubuntu-22.04.qcow2" : var.vm_template_name
}

variable "infrahub_version" {
  type    = string
  default = ""
}

variable "vm_template_name" {
  type    = string
  default = ""
}

source "qemu" "custom_image" {
  # Boot Commands when Loading the ISO file with OVMF.fd file (Tianocore) / GrubV2
  boot_command = [
    "<spacebar><wait><spacebar><wait><spacebar><wait><spacebar><wait><spacebar><wait>",
    "e<wait>",
    "<down><down><down><end>",
    " autoinstall ds=nocloud-net\\;s=http://{{ .HTTPIP }}:{{ .HTTPPort }}/",
    "<f10>"
  ]
  boot_wait = "5s"

  output_directory = "output"
  http_directory   = "http"
  iso_url          = "https://releases.ubuntu.com/jammy/ubuntu-22.04.4-live-server-amd64.iso"
  iso_checksum     = "file:https://releases.ubuntu.com/jammy/SHA256SUMS"
  memory           = 4096

  ssh_password = "packerubuntu"
  ssh_username = "admin"
  ssh_timeout  = "20m"

  headless         = true
  accelerator      = "kvm"
  format           = "qcow2"
  disk_compression = true

  disk_image = false
  disk_size  = "20G"

  cpu_model = "host"
  sockets   = 1
  cpus      = 8
  cores     = 8
  threads   = 1

  qemu_img_args {
    convert = ["-W"] # should speedup compression according to: https://gitlab.com/qemu-project/qemu/-/issues/80#note_1669835297
  }

  vm_name = local.vm_template_name
}

build {
  sources = ["source.qemu.custom_image"]
  provisioner "shell" {
    inline = ["while [ ! -f /var/lib/cloud/instance/boot-finished ]; do echo 'Waiting for Cloud-Init...'; sleep 1; done"]
  }

  provisioner "ansible" {
    user          = build.User
    playbook_file = "${path.cwd}/ansible/bootstrap_infra.yml"
    command       = "./ansible-playbook.sh"
    ansible_env_vars = [
      "ANSIBLE_HOST_KEY_CHECKING=False"
    ]

    extra_arguments = [
      "-e", "infrahub_dir=/opt/infrahub",
      "-e", "expose_database_ports=false",
      "-e", "expose_message_queue_ports=false",
      "-e", "NEO4J_PASSWORD=admin",
      "-e", "RABBITMQ_PASSWORD=admin",
      "-e", "INFRAHUB_CONTAINER_REGISTRY=9r2s1098.c1.gra9.container-registry.ovh.net",
      "-e", "INFRAHUB_VERSION=${local.infrahub_version}",
      "-e", "INFRAHUB_PRODUCTION=false",
      "-e", "INFRAHUB_SECURITY_INITIAL_ADMIN_TOKEN=1b93a1e6-b14a-4c5b-b16e-e154d6ed05f4",
      "-e", "INFRAHUB_SECURITY_SECRET_KEY=1b93a1e6-b14a-4c5b-b16e-e154d6ed05f4",
    ]


    galaxy_command = "./ansible-galaxy.sh"
    galaxy_file    = "${path.cwd}/ansible/requirements.yml"
  }

  provisioner "ansible" {
    user          = build.User
    playbook_file = "${path.cwd}/ansible/bootstrap_monitoring_stack.yml"
    command       = "./ansible-playbook.sh"
    ansible_env_vars = [
      "ANSIBLE_HOST_KEY_CHECKING=False"
    ]

    extra_arguments = [
      "-e", "node_exporter_web_listen_address=127.0.0.1:9100",
      "-e", "install_vector=true",
      "-e", "monitor_infrahub=true",
      "-e", "GRAFANA_ROOT_URL=''",
    ]


    galaxy_command = "./ansible-galaxy.sh"
    galaxy_file    = "${path.cwd}/ansible/requirements.yml"
  }

  provisioner "shell" {
    inline = [
      "sudo sed -i 's/GRUB_CMDLINE_LINUX_DEFAULT=\".*\"/GRUB_CMDLINE_LINUX_DEFAULT=\"\"/' /etc/default/grub",
      "sudo update-grub2",
      "sudo passwd -d ${build.User}",
      "sudo apt-get -y autoremove --purge",
      "sudo apt-get -y clean",
      "sudo apt-get -y autoclean",
      "sudo cloud-init clean -l -s -c all",
      "sudo sync",
    ]
  }
}

