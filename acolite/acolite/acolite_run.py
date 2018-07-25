## def acolite_run
## wrapper script to launch acolite processing: tile merging, a/c, rgb and l2w output
##
## Written by Quinten Vanhellemont 2017-11-30
## Last modifications: 2018-03-07 (QV) renamed from acolite
##                     2018-04-18 (QV) changed RGB mapping script
##                     2018-04-19 (QV) added RGB pan sharpening
##                     2018-06-06 (QV) added xy outputs, rhorc check
##                     2018-06-15 (QV) fixed check for olh and rhorc when parameters=None
##                     2018-07-18 (QV) changed acolite import name
##                     2018-07-24 (QV) added l2w_mask_negative_rhow

def acolite_run(inputfile=None, output=None, limit=None, merge_tiles=None, settings=None, quiet=False, ancillary=False, gui=False):
    import os, sys
    import datetime, time

    from acolite import acolite
    from acolite.output import nc_to_geotiff

    print('Launching ACOLITE Python!')
    setu = acolite.acolite_settings(settings)
    #print(setu)

    ## set variables from settings file if not directly provided by user
    if (inputfile is not None): setu['inputfile'] = inputfile
    if (output is not None): setu['output'] = output
    if (merge_tiles is not None): setu['merge_tiles'] = merge_tiles 
    if (limit is not None): setu['limit'] = limit

    #if 'ancillary' not in setu:
    #    setu['ancillary'] = ancillary
    if 'l2w_parameters' not in setu:
        setu['l2w_parameters'] = None

    if setu['l2w_parameters'] is not None:
        if ('bt10' in setu['l2w_parameters']) or ('bt11' in setu['l2w_parameters']):
            setu['l8_output_bt'] = True

    if (gui) & (setu['ancillary_data']): 
        print('Disabling ancillary data in GUI due to download bug.')
        print('Please use the CLI for ancillary download.')
        setu['ancillary_data'] = False

    ## check if we have an inputfile
    if (setu['inputfile'] is None):
        print('No inputfile given. Exiting.')
        raise BaseException('InputError')
    
    ## set output if not defined
    if ('output' not in setu): 
        setu['output'] = os.path.dirname(inputfile[0])

    ## force limit to None if not provided
    if ('limit' not in setu): 
        setu['limit'] = None

    ## make gains into list of floats
    for key in setu:
        if 'gains_' in key:
             setu[key] = [float(i) for i in setu[key]]

    ## test access to output directory
    try:
        if not os.path.exists(setu['output']): os.makedirs(setu['output'])
    except:
        print('No write access to the output directory: {}'.format(setu['output']))
        raise BaseException('WriteError')
    
    ## time of processing start
    time_start = datetime.datetime.now()
    time_start_str = time_start.strftime('%Y_%m_%d_%H_%M_%S')
    if 'runid'not in setu: setu['runid']=time_start.strftime('%Y%m%d_%H%M%S')
    
    print('Started ACOLITE Python processing')

    ## write settings
    sf = '{}/acolite_run_{}_settings.txt'.format(setu['output'],setu['runid'])
    acolite.settings_write(sf, setu)
    print('Wrote run settings file to {}'.format(sf))

    ## convert inputfile into a list
    inputfile = setu['inputfile'] if type(setu['inputfile']) is list else [setu['inputfile']]
    
    l8_output_pan_ms, l8_output_orange, nc_write_rhorc = False, False, False
    if (setu['l2w_parameters'] is not None):
        ## check if rhorc output is needed
        nc_write_rhorc = any(['rhorc_' in p for p in setu['l2w_parameters']])
        ## check if we need olh output
        orange_output = any([p in setu['l2w_parameters'] for p in ['rhot_613','rhorc_613','rhos_613', 'rhow_613']])
        olh_output = any([p in setu['l2w_parameters'] for p in ['olh']])
        l8_output_pan_ms = orange_output | olh_output
        l8_output_orange = orange_output | olh_output
        print(setu['l2w_parameters'])
        print(l8_output_pan_ms)

    ## merge the given tiles if requested
    if setu['merge_tiles']:
        if setu['limit'] is None:
            print('Merging not supported without specified region of interest limit.')
            raise BaseException('MergeError:Region')
        ni = len(inputfile)
        print('Merging {} tile{}...'.format(ni,'' if ni == 1 else 's'))
        ### run toa crop netcdf for these scenes and limit
        scenes = acolite.acolite_toa_crop(inputfile, setu['output'], 
                                          limit=setu['limit'], 
                                          s2_target_res=setu['s2_target_res'], 
                                          l8_output_pan=setu['rgb_pan_sharpen'], 
                                          l8_output_pan_ms=l8_output_pan_ms,
                                          nc_write_geo_xy=setu['xy_output'])
        if type(scenes) is int:
            print('Error merging scene {}'.format(inputfile))
            raise BaseException('MergeError:FileNotRecognised')

        print('Finished merging {} tile{}.'.format(ni,'' if ni == 1 else 's'))
        setu['limit'] = None
    else:
        scenes = inputfile

    ## make sure scenes is a list
    if type(scenes) is not list: scenes = [scenes]

    ## run processing for scenes
    l2r_files = []
    nsc = len(scenes)

    print('Processing {} scene{}...'.format(nsc, '' if nsc == 1 else 's'))
    for sc, scene in enumerate(scenes):
        print('Processing scene {} of {}...'.format(sc+1, nsc))

        ## run acolite_py with given settings dict for this scene
        ret = acolite.acolite_ac(scene, setu['output'], limit=setu['limit'], 
                                                        ## select aerosol correction
                                                        aerosol_correction=setu['aerosol_correction'], 

                                                        ## generic settings
                                                        ancillary_data=setu['ancillary_data'],
                                                        gas_transmittance=setu['gas_transmittance'],
                                                        uoz_default=float(setu['uoz_default']),
                                                        uwv_default=float(setu['uwv_default']),
                                                        sky_correction=setu['sky_correction'],
                                                        sky_correction_option=setu['sky_correction_option'],
                                                        pressure=setu['pressure'],
                                                        lut_pressure=setu['lut_pressure'],
                                                        dem_pressure=setu['dem_pressure'],
                                                        dem_pressure_percentile=setu['dem_pressure_percentile'],

                                                        ## for dark spectrum
                                                        dsf_path_reflectance=setu['dsf_path_reflectance'],
                                                        dsf_spectrum_option=setu['dsf_spectrum_option'],
                                                        dsf_full_scene=setu['dsf_full_scene'],
                                                        dsf_model_selection=setu['dsf_model_selection'],
                                                        dsf_list_selection=setu['dsf_list_selection'],
                                                        dsf_tile_dims=setu['dsf_tile_dims'],
                                                        dsf_min_tile_cover=float(setu['dsf_min_tile_cover']),
                                                        dsf_min_tile_aot=float(setu['dsf_min_tile_aot']),
                                                        dsf_plot_retrieved_tiles=setu['dsf_plot_retrieved_tiles'],
                                                        dsf_plot_dark_spectrum=setu['dsf_plot_dark_spectrum'],
                                                        dsf_write_tiled_parameters=setu['dsf_write_tiled_parameters'],

                                                        ## for exponential
                                                        exp_swir_threshold=float(setu['exp_swir_threshold']),
                                                        exp_fixed_epsilon=setu['exp_fixed_epsilon'],
                                                        exp_fixed_epsilon_percentile=float(setu['exp_fixed_epsilon_percentile']),
                                                        exp_fixed_aerosol_reflectance=setu['exp_fixed_aerosol_reflectance'],
                                                        exp_fixed_aerosol_reflectance_percentile=float(setu['exp_fixed_aerosol_reflectance_percentile']),
                                                        exp_wave1=float(setu['exp_wave1']),
                                                        exp_wave2=float(setu['exp_wave2']),
                                                        exp_alpha=setu['exp_alpha'],
                                                        exp_alpha_weighted=setu['exp_alpha_weighted'],
                                                        exp_epsilon=setu['exp_epsilon'],

                                                        ## Gains
                                                        gains=setu['gains'],
                                                        gains_l5_tm=setu['gains_l5_tm'],
                                                        gains_l7_etm=setu['gains_l7_etm'],
                                                        gains_l8_oli=setu['gains_l8_oli'],
                                                        gains_s2a_msi=setu['gains_s2a_msi'],
                                                        gains_s2b_msi=setu['gains_s2b_msi'],

                                                        ## NetCDF compression
                                                        l1r_nc_compression=setu['l1r_nc_compression'],
                                                        l2r_nc_compression=setu['l2r_nc_compression'],

                                                        ## Sentinel-2 output resolution
                                                        s2_target_res=setu['s2_target_res'],
                                                        ## L8 output BT
                                                        l8_output_bt=setu['l8_output_bt'],
                                                        ## L8 output PAN band
                                                        l8_output_pan=setu['rgb_pan_sharpen'],
                                                        l8_output_pan_ms=l8_output_pan_ms, 
                                                        l8_output_orange=l8_output_orange,
                                                        ## output of easting and northing
                                                        nc_write_geo_xy=setu['xy_output'],
                                                        ## output Rayleigh corrected reflectances
                                                        nc_write_rhorc=nc_write_rhorc
                                                        )
        l2r_files+=ret

        ## output GeoTIFF
        if setu['l2r_export_geotiff']:
            if type(ret) is not list: ret = [ret]
            for f in ret: nc_to_geotiff(f)

        ## map RGB
        if setu['rgb_rhot'] or setu['rgb_rhos']:
            print('Mapping RGB from {}'.format(ret[0]))
            for retf in ret: 
                #acolite.acolite_rgb(ret[0], setu['output'], map_rhot=setu['rgb_rhot'], map_rhos=setu['rgb_rhos'], map_title=setu['map_title'])
                acolite.acolite_map(ret[0], setu['output'], rgb_rhot=setu['rgb_rhot'], rgb_rhos=setu['rgb_rhos'], 
                                         map_title=setu['map_title'], 
                                         map_colorbar=setu['map_colorbar'], 
                                         map_colorbar_orientation=setu["map_colorbar_orientation"],
                                         mapped=setu["map_projected"], map_raster=setu["map_raster"],
                                         map_scalebar=setu["map_scalebar"],
                                         map_scalepos=setu["map_scalepos"],
                                         map_scalecolor_rgb=setu["map_scalecolor_rgb"],
                                         map_scalelen=setu["map_scalelen"],
                                         map_colorbar_edge=setu["map_colorbar_edge"],
                                         max_dim=float(setu["map_max_dim"]),
                                         map_points=setu["map_points"],
                                         red_wl=float(setu["rgb_red_wl"]),
                                         green_wl=float(setu["rgb_green_wl"]),
                                         blue_wl=float(setu["rgb_blue_wl"]),
                                         rgb_min=[float(i) for i in setu["rgb_min"]],
                                         rgb_max=[float(i) for i in setu["rgb_max"]], rgb_pan_sharpen=setu['rgb_pan_sharpen'])

    ## output L2W products
    l2r_nsc = len(l2r_files)
    if (setu['l2w_parameters'] is not None) and (l2r_nsc > 0):
    	if len(setu['l2w_parameters']) > 0:
            if type(setu['l2w_parameters']) is not list: setu['l2w_parameters']=[setu['l2w_parameters']]
            l2w_files = []
            print('Computing L2W parameters for {} scene{}...'.format(l2r_nsc, '' if l2r_nsc == 1 else 's'))
            print('L2W parameters: {}'.format(', '.join(setu['l2w_parameters'])))

            for sc, scene in enumerate(l2r_files):
                print('Computing L2W parameters for scene {} of {}...'.format(sc+1, l2r_nsc))
                print(scene)
                ret = acolite.acolite_l2w(scene, setu['output'], parameters=setu['l2w_parameters'], retain_data_read=True,
                                          l2w_mask=setu['l2w_mask'],
                                          l2w_mask_wave=float(setu['l2w_mask_wave']),
                                          l2w_mask_threshold=float(setu['l2w_mask_threshold']),
                                          l2w_mask_water_parameters=setu['l2w_mask_water_parameters'],
                                          l2w_mask_negative_rhow=setu['l2w_mask_negative_rhow'],
                                          nc_compression=setu['l2w_nc_compression'],)
                if type(ret) is not list: ret = [ret]
                l2w_files+=ret

                ## output GeoTIFF
                if setu['l2w_export_geotiff']:
                    for f in ret: nc_to_geotiff(f)
                print(ret)

                ## map l2w parameters
                if setu['map_l2w']:
                    for f in ret:
                        print('Mapping L2W parameters from {}'.format(f))
                        acolite.acolite_map(f, setu['output'], parameters=setu['l2w_parameters'], 
                                             auto_range=setu['map_auto_range'], 
                                             map_title=setu['map_title'], 
                                             map_colorbar=setu['map_colorbar'], 
                                             map_colorbar_orientation=setu["map_colorbar_orientation"],
                                             mapped=setu["map_projected"], map_raster=setu["map_raster"],
                                             map_scalebar=setu["map_scalebar"],
                                             map_scalepos=setu["map_scalepos"],
                                             map_scalecolor=setu["map_scalecolor"],
                                             map_scalelen=setu["map_scalelen"],
                                             map_colorbar_edge=setu["map_colorbar_edge"],
                                             max_dim=float(setu["map_max_dim"]),
                                             map_points=setu["map_points"], map_fillcolor=setu['map_fillcolor'], 
                                             rgb_pan_sharpen=setu['rgb_pan_sharpen'])

    ## done
    print('Finished processing {} scene{}.'.format(nsc,'' if nsc == 1 else 's'))
    return(0)