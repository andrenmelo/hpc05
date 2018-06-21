# Standard library imports
import contextlib
import os
import shutil
import subprocess
import sys
import textwrap

# Third party imports
from IPython.paths import locate_profile

# Local imports
from .ssh_utils import get_info_from_ssh_config, setup_ssh
from .utils import bash


def line_prepender(filename, line):
    if isinstance(line, list):
        line = "\n".join(line)
    with open(filename, 'r') as f:
        content = f.read()
    with open(filename, 'w') as f:
        f.write(line + '\n' + content)


def create_parallel_profile(profile):
    cmd = [sys.executable, "-E", "-c", "from IPython import start_ipython; start_ipython()",
           "profile", "create", profile, "--parallel"]
    subprocess.check_call(cmd)


def create_slurm_profile(profile='slurm', local_controller=False, custom_template=None):
    """Creata a slurm profile.

    Custom template example:

    custom_template = '''\
        #!/bin/sh
        #SBATCH --ntasks={n}
        #SBATCH --mem-per-cpu=4G
        #SBATCH --job-name=ipy-engine-
        srun ipengine --profile-dir='{profile_dir}' --cluster-id=''
    '''
    """
    with contextlib.suppress(FileNotFoundError):
        shutil.rmtree(os.path.expanduser(f'~/.ipython/profile_{profile}'))
    create_parallel_profile(profile)

    default_template = """\
        #!/bin/sh
        #SBATCH --ntasks={n}
        #SBATCH --mem-per-cpu=4G
        #SBATCH --job-name=ipy-engine-
        srun ipengine --profile-dir='{profile_dir}' --cluster-id=''
    """
    template = textwrap.dedent(custom_template or default_template)

    ipcluster = ["c.IPClusterEngines.engine_launcher_class = 'SlurmEngineSetLauncher'",
                 f'c.SlurmEngineSetLauncher.batch_template = """{template}"""']
    
    if not local_controller:
        ipcluster.append("c.IPClusterStart.controller_launcher_class = 'SlurmControllerLauncher'")

    f = {'ipcluster_config.py': ipcluster,
         'ipcontroller_config.py': ["c.HubFactory.ip = u'*'",
                                    "c.HubFactory.registration_timeout = 600"],
         'ipengine_config.py': ["c.IPEngineApp.wait_for_url_file = 300",
                                "c.EngineFactory.timeout = 300",
                                "c.IPEngineApp.startup_command = 'import os, sys'"]}

    for fname, line in f.items():
        fname = os.path.join(locate_profile(profile), fname)
        line_prepender(fname, line)

    print(f'Succesfully created a new {profile} profile.')


def create_remote_slurm_profile(hostname='hpc05', username=None, password=None,
                                profile="slurm", local_controller=False,
                                custom_template=None):
    if custom_template is not None:
        raise NotImplementedError('Use `create_slurm_profile` locally or implement this.')
    with setup_ssh(hostname, username, password) as ssh:
        cmd = f'import hpc05; hpc05.slurm_profile.create_slurm_profile("{profile}", {local_controller})'
        cmd = f"python -c '{cmd}'"
        stdin, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
        out, err = stdout.readlines(), stderr.readlines()

        for lines in [out, err]:
            for line in lines:
                print(line.rstrip('\n'))
