#!/usr/bin/python3

from tempfile import mkdtemp
from git import Git, Repo, cmd
from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from xml.dom import minidom
from sys import argv
from os import environ
import re

major_version="9"
kernel_device=environ['KERNEL']
kernel_manifest_url="https://android.googlesource.com/kernel/manifest"
kernel_manifest_exp="origin/android-msm-%s" % kernel_device
platform_manifest_url="https://android.googlesource.com/platform/manifest"
platform_manifest_exp="origin/android-%s" % major_version
platform_extra_remotes = [
    { "name": "github" ,"fetch": "https://github.com/" },
    { "name": "gitlab" ,"fetch": "https://gitlab.com/" },
]
platform_extra_projects = [
    {
        "name": "fdroid/fdroidclient",
        "groups": "device",
        "path": "packages/apps/F-Droid",
        "remote": "gitlab",
        "revision": "refs/tags/1.4"
    },
    {
        "name": "fdroid/privileged-extension",
        "groups": "device",
        "path": "packages/apps/F-DroidPrivilegedExtension",
        "remote": "gitlab",
        "revision": "refs/tags/0.2.8"
    },
]

class AndroidManifest:

    def __init__(self, url, exp, extra_remotes=[], extra_projects=[]):
        self.url = url
        self.exp = exp
        self.extra_remotes = extra_remotes
        self.extra_projects = extra_projects
        self._fetch()
        self._extend()
        self._set_remotes()
        self._set_default_remote()
        self._set_default_revision()
        self._lock()

    def _fetch(self):
        repo = Repo.clone_from(self.url, mkdtemp())
        ref = [
            str(ref) for ref in
            sorted(repo.refs, key=lambda t: t.commit.committed_datetime)
            if re.match(self.exp, str(ref))
        ][-1]
        repo.head.reference = repo.commit(ref)
        string = repo.git.show('HEAD:default.xml')
        self.manifest = ElementTree.fromstring(string)

    def _extend(self):
        for remote in self.extra_remotes:
            element = Element("remote")
            element.attrib = remote
            self.manifest.insert(1,element)
        for project in self.extra_projects:
            element = Element("project")
            element.attrib = project
            self.manifest.insert(4,element)

    def _set_remotes(self):
        self.remotes={}
        remote_nodes = self.manifest.findall(".//remote")
        for remote_node in remote_nodes:
            if 'review' in remote_node.attrib:
                self.remotes[remote_node.attrib["name"]] = \
                    remote_node.attrib["review"]
            else:
                self.remotes[remote_node.attrib["name"]] = \
                    remote_node.attrib["fetch"]

    def _set_default_revision(self):
        self.default_revision = \
            revision=self.manifest.findall(".//default")[0].attrib['revision']

    def _set_default_remote(self):
        default_remote_name = \
            self.manifest.findall(".//default")[0].attrib['remote']
        self.default_remote = self.remotes[default_remote_name]

    def _lock(self):
        projects=self.manifest.findall(".//project")
        for project in projects:
            if 'remote' in project.attrib:
                remote = self.remotes[project.attrib['remote']]
            else:
                remote = self.default_remote
            if 'revision' in project.attrib:
                revision = project.attrib['revision']
            else:
                revision = self.default_revision
            if 'refs' not in revision:
                revision = "refs/heads/%s" % revision
            project_repo_url="%s%s.git" % (remote, project.attrib['name'])
            remote_refs = self._lsremote(project_repo_url)
            project.attrib['upstream'] = revision
            project.attrib['revision'] = remote_refs[revision]

    def _lsremote(self, url):
        remote_refs = {}
        g = cmd.Git()
        for ref in g.ls_remote(url).split('\n'):
            hash_ref_list = ref.split('\t')
            remote_refs[hash_ref_list[1]] = hash_ref_list[0]
        return remote_refs

    def pretty_print(self):
        rough_string = ElementTree.tostring(self.manifest, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", newl="")

if __name__ == "__main__":

    kind=argv[1]

    if kind == 'kernel':
        manifest = AndroidManifest(
            kernel_manifest_url,
            kernel_manifest_exp
        ).pretty_print()
    elif kind == 'platform':
        manifest = AndroidManifest(
            platform_manifest_url,
            platform_manifest_exp,
            platform_extra_remotes,
            platform_extra_projects
        ).pretty_print()

    if manifest:
        print(manifest)