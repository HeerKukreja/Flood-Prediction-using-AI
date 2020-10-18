# This scripts runs the terrain analysis steps to create the HAND map.

import arcpy
import os
import sys
import time

def main(in_dir, out_dir, dem_dir, hydrog_dir, info1, info2, info3, info4, info5, info6):
    arcpy.env.overwriteOutput = True

    # Create the output directory
    if not os.path.isdir(os.getcwd() + out_dir):
        os.makedirs(os.getcwd() + out_dir)

    # Step 1. Use "raster domain" tool from arcpy and create a domain shapefile from the DEM raster file.
    print("Start the pre-processing steps")
    arcpy.RasterDomain_3d(in_raster=os.path.normpath(os.getcwd()+os.sep+os.pardir+os.sep+os.pardir) + dem_dir + info1,
                          out_feature_class=os.getcwd() + out_dir + info2,
                          out_geometry_type="POLYGON")

    # Step 2. Select the domain shapefile and define an internal buffer of the domain shapefile using "buffer" tool.
    # Remember to use negative sign for the internal buffer.
    arcpy.Buffer_analysis(in_features=os.getcwd() + out_dir + info2,
                          out_feature_class=os.getcwd() + out_dir + info3,
                          buffer_distance_or_field=info4,
                          line_side="FULL",
                          line_end_type="ROUND",
                          dissolve_option="NONE",
                          dissolve_field="",
                          method="GEODESIC")

    # Step 3. Use "select by attribute" tool to exclude the canals.
    name = os.path.normpath(os.getcwd()+os.sep+os.pardir+os.sep+os.pardir) + hydrog_dir + info5
    name_temp = name.replace('.shp', '_lyr')
    arcpy.MakeFeatureLayer_management(name, name_temp)
    medres_NHDPlusflowline_noCanal = arcpy.SelectLayerByAttribute_management(name_temp, 'NEW_SELECTION', "FTYPE <> " + info6)

    # Step 4. Clip the medium-resolution NHD (i.e., medres_NHDPlusflowline.shp) for the "internal250mbuffer.shp".
    arcpy.Clip_analysis(in_features=medres_NHDPlusflowline_noCanal,
                        clip_features=os.getcwd() + out_dir + info3,
                        out_feature_class=os.getcwd() + out_dir + 'medres_NHDPlusflowline_noCanal_to_bfr.shp',
                        cluster_tolerance="")

    # Step 5. Find the starting points (dangles) that are used as an input to the network delineation process.
    #         In this research study, we used the main stems for the dangles. This was done within the ArcGIS software
    #         and the results are here as input files for the next steps. Following comment explains the steps we took
    #         in the ArcGIS software to create these files.

    #         1.Select the dangles (using "feature vertices to points" tool and set point_location="DANGLE").
    #         These are going to be used as the starting points to delineate the stream network. In our work, we only
    #         considered the main stems when generating the dangle points. This is due to the fact that the main stems
    #         had larger contributing areas in our case studies compared to the side tributaries.

    #         2.Open the attribute table of the dangle shapefile. Add a field using "add field" tool. Then, use
    #         "calculate field" tool to put a value of 1 for all the rows in this field.

    #         3.Use "feature to raster" tool to rasterize the dangle points. Make sure to set the extent and snap
    #         raster sizes to be the same as the DEM size (an extracted DEM that covers the domain) in the enviroment
    #         settings of the tool.

    #         4.Use the "reclassify" tool to reclassify the inlets.tif raster layer so that 1 is one and the rest (
    #         i.e., 0 or NAN) is zero.

    # Step 6. Generate the evenly dispersed nodes along the main stem.
    #         The evenly dispersed nodes are used as an input to the network delineation process. This was done within
    #         the ArcGIS software and the results are here as input files for the next steps. Following comment explains
    #         the steps we took in the ArcGIS software to create these nodes.

    #         1.Select the main stem from the buffered medium resolution NHDPlus
    #         dataset and save it as a new feature. Then, use "dissolve" tool to merge the segments (reaches) of this
    #         new feature into one single segment. Next, use "editor -> split" tool to split this feature into smaller
    #         equal segments with 3 km long. Then, create a new point shapefile and use the editor tool to generate
    #         points on the upstream and downstream ends of these equal segments. The new shape file is the evenly
    #         dispersed nodes on the main stems. This is required when delineating the stream network and catchments.

    # Step 7. Using a non-conditioned DEM and calculating the HAND using the following procedure.

    # 1.Fill pits in the original dem
    print('Running PitRemove Function')
    i_path = os.path.normpath(os.getcwd()+os.sep+os.pardir+os.sep+os.pardir) + dem_dir + info1
    o_path = os.getcwd() + out_dir + "fel.tif"
    bashCommand = "mpiexec -n 10 PitRemove -z " + i_path + " -fel " + o_path
    os.system(bashCommand)
    time.sleep(120)

    # 2.Compute the D8 flow direction.
    print('Running D8 Flow Direction Function')
    i_path = os.getcwd() + out_dir + "fel.tif"
    o1_path = os.getcwd() + out_dir + "p.tif"
    o2_path = os.getcwd() + out_dir + "sd8.tif"
    bashCommand = "mpiexec -n 10 D8FlowDir -fel " + i_path + " -p " + o1_path + " -sd8 " + o2_path
    os.system(bashCommand)
    time.sleep(360)

    # 3.Compute D8 area contributing Compute D8 area contributing.
    print('Running D8 Area Contributing Function')
    i1_path = os.getcwd()+in_dir + "inlets_on_mainstem.tif"
    i2_path = os.getcwd()+out_dir + "p.tif"
    o_path = os.getcwd()+out_dir + "ad8.tif"
    bashCommand = "mpiexec -n 10 Aread8 -wg " + i1_path + " -p " + i2_path + " -ad8 " + o_path + " -nc "
    os.system(bashCommand)
    time.sleep(120)

    # 4.Use a threshold to delineate the stream
    print('Running Network Delineation Function')
    i_path = os.getcwd() + out_dir + "ad8.tif"
    o_path = os.getcwd() + out_dir + "src.tif"
    bashCommand = "mpiexec -n 10 Threshold -ssa " + i_path + " -src " + o_path + " -thresh 1"
    os.system(bashCommand)
    time.sleep(120)

    # 5.Generate network and watershed
    i1_path = os.getcwd() + in_dir + "Evenly_dispersed_nodes.shp"
    i2_path = os.getcwd() + out_dir + "fel.tif"
    i3_path = os.getcwd() + out_dir + "p.tif"
    i4_path = os.getcwd() + out_dir + "ad8.tif"
    i5_path = os.getcwd() + out_dir + "src.tif"
    o1_path = os.getcwd() + out_dir + "ord.tif"
    o2_path = os.getcwd() + out_dir + "tree.dat"
    o3_path = os.getcwd() + out_dir + "coord.dat"
    o4_path = os.getcwd() + out_dir + "net.shp"
    o5_path = os.getcwd() + out_dir + "w.tif"
    bashCommand = "mpiexec -n 10 Streamnet -o " + i1_path + " -fel " + i2_path + " -p " + i3_path + \
                  " -ad8 " + i4_path + " -src " + i5_path + " -ord " + o1_path + " -tree " + o2_path + \
                  " -coord " + o3_path + " -net " + o4_path + " -w " + o5_path
    os.system(bashCommand)

    # 6.Compute the D-inf flow direction. This function may take several hours to run.
    print('Running D-infinity Flow Direction Function')
    i_path = os.getcwd() + out_dir + "fel.tif"
    o1_path = os.getcwd() + out_dir + "ang.tif"
    o2_path = os.getcwd() + out_dir + "slp.tif"
    bashCommand = "mpiexec -n 10 DinfFlowDir -fel " + i_path + " -ang " + o1_path + " -slp " + o2_path
    os.system(bashCommand)
    time.sleep(360)

    # 7.Compute the HAND using D-inf Distance Down.
    print('Running D-infinity Distance Down Function to calculate HAND')
    i1_path = os.getcwd() + out_dir + "fel.tif"
    i2_path = os.getcwd() + out_dir + "src.tif"
    i3_path = os.getcwd() + out_dir + "ang.tif"
    o_path = os.getcwd() + out_dir + "hand.tif"
    bashCommand = "mpiexec -n 10 DinfDistDown -fel " + i1_path + " -src " + i2_path + " -ang " + i3_path + " -m ave v " + " -dd " + o_path + " -nc "
    os.system(bashCommand)
    time.sleep(360)

    print('Done!')

if __name__ == '__main__':
    in_dir = sys.argv[1]
    out_dir = sys.argv[2]
    dem_dir = sys.argv[3]
    hydrog_dir = sys.argv[4]
    info1 = sys.argv[5]
    info2 = sys.argv[6]
    info3 = sys.argv[7]
    info4 = sys.argv[8]
    info5 = sys.argv[9]
    info6 = sys.argv[10]


    main(in_dir, out_dir, dem_dir, hydrog_dir, info1, info2, info3, info4, info5, info6)





