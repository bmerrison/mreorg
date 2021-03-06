
import models
from django.db import transaction
import os
import mreorg

def from_default_monitor_dirs():
    #default_filegroups = mreorg.MReOrgConfig.get_ns().get('default_filegroups',{})
    #for fgname, fgglobs in default_filegroups.iteritems():
    pass


@classmethod
@transaction.commit_on_success
def update_all_db(cls, directory):

    print 'Updating untracked simulation files', directory
    for (dirpath, dirnames, filenames) in os.walk( directory ):
        for filename in filenames:
            if not filename.endswith(".py"):
                continue
            full_filename = os.path.join( dirpath, filename ) 
            if mreorg.MReOrgConfig.is_non_curated_file(filename):
                continue
            if mreorg.MReOrgConfig.is_non_curated_file(full_filename):
                continue

            try:
                models.SimFile.objects.get(full_filename=full_filename)
            except models.SimFile.DoesNotExist:
                models.SimFile.create(full_filename=full_filename, tracked=False)

def update_db_from_config():
    import mreorg
    from mreorg.curator.frontend.models import RunConfiguration, FileGroup, SimFile
    from mreorg.curator.frontend.models import EnvironVar

    # Update the FileGroups:
    default_filegroups = mreorg.MReOrgConfig.get_ns().get('default_filegroups',{})
    for fgname, fgglobs in default_filegroups.iteritems():
        filenames = set()
        for fgglob in fgglobs:
            filenames.update(mreorg.glob2.glob(fgglob) )

        # Safely get the FileGroup:
        fg = FileGroup.get_or_make(name=fgname)
        assert not fg.is_special(), 'Trying to overwrite a builtin filegroup'
        for filename in filenames:
            simfile = SimFile.get_or_make(full_filename=filename)
            if not fg.contains_simfile(simfile):
                fg.simfiles.add(simfile)
                fg.save()

        print 'Updated FileGroup: %s' % (fgname,)


    # Update the RunConfigurations:
    default_runconfigs = mreorg.MReOrgConfig.get_ns().get('default_runconfigs',{})
    for confname, confinfo in default_runconfigs.iteritems():
        runconf = RunConfiguration.get_or_make(name=confname)
        assert not runconf.is_special(), 'Trying to add a builtin-configuration'
        runconf.timeout = confinfo.get('timeout',None)

        for (key, value) in confinfo.get('env_vars',{}).iteritems():
            try:
                envvar = runconf.environvar_set.get(key=key)
                envvar.value = value
                envvar.save()
            except EnvironVar.DoesNotExist:
                envvar = EnvironVar(key=key,value=value,config=runconf)
                envvar.save()

        runconf.save()
        print 'Updated RunConfig: %s' % confname

        # Add default locations:
        mh_adddefault_locations()
        # Rescan-filesystem:
        rescan_filesystem()

        print 'Finished Reconfiguring'





def rescan_filesystem():
    for src_dir in models.SourceSimDir.objects.all():
        models.SimFile.update_all_db(src_dir.directory_name)



def mh_adddefault_locations():
    import mreorg
    default_simulations = mreorg.MReOrgConfig.get_ns().get('default_simulations', [])

    for l in default_simulations:
        if not l:
            continue
        if l[-1] != '*':
            models.SimFile.get_or_make(full_filename=l, make_kwargs={'tracking_status': models.TrackingStatus.Tracked} )
        elif l.endswith('**'):
            models.SourceSimDir.create(directory_name=l[:-2],
                                should_recurse=True)
        elif l.endswith('*'):
            models.SourceSimDir.create(directory_name=l[:-1],
                                should_recurse=False)
        else:
            models.SourceSimDir.create(directory_name=l[:-2],
                                should_recurse=False)
