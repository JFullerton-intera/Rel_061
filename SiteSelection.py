'''----------------------------------------------------------------------------------
 Tool Name:   Site-Specific Recharge Estimates
 Source Name: SSRecharge2017_v01.py
 Version:     ArcGIS 10.3
 Author:      INTERA Inc.
 Required Arguments:
              One feature classes:
                  Model Domain
              Two Values:
                  Simulation Start Year
                  Simulation Duration (years)
              Two directories:
                  Input (path to RET outputs)
                  Output (path to site-specifc recharge estimates)
 Description: Creates a series of recharge estimates for a user-specified model domain and simulation period 
              by identifying years of interest (YoI) within the simulation period for the sites within the model 
              domain & clipping RET outputs for these years to the user's model domain.  
----------------------------------------------------------------------------------'''

# Import modules
import os
import arcpy
import csv
from datetime import datetime

#Allow for overwriting of outputs
arcpy.env.overwriteOutput = True

#Get working directory
working_dir = os.path.dirname(os.path.realpath(__file__))

#Print start time
start = datetime.now()
print start

##############################################################################
#Step 1. Read in user's model domain, simulation period, and output folder
#Model Domain
AoI = arcpy.GetParameterAsText(0) 
#Simulation Start Year
simyear_input = arcpy.GetParameterAsText(1)
#Simulation Duration (years)
simduration_input = arcpy.GetParameterAsText(2)
#Source Geodatabase
source_gdb = arcpy.GetParameterAsText(3)
#Input directory
in_workspace_input = arcpy.GetParameterAsText(4)
#Output directory
out_workspace_input = arcpy.GetParameterAsText(5)
#Model nickname
m_name_input = arcpy.GetParameterAsText(6)

#Set default values if optional fields left blank
if not AoI:
    AoI = os.path.join(working_dir, 'GIS\shp\U8_Area.shp')
try: 
    simyear = int(simyear_input)
except: 
    simyear = 1943
try: 
    simduration = int(simduration_input)
except: 
    simduration = 2000
in_workspace = in_workspace_input
if not in_workspace:
    in_workspace = os.path.join(working_dir, 'Outputs\Outputs_v05')
m_name = m_name_input
if not m_name:  
    m_name = datetime.now().strftime("%Y%m%d_%H%M%S")
out_workspace = out_workspace_input
if not out_workspace:
    out_workspace = os.path.join(working_dir, 'Outputs\Outputs_ModelSpecific')

# Create Output Directory if doesn't exist
if not os.path.exists(out_workspace):
    os.makedirs(out_workspace)

# Create Geodatabase if doesn't exist
out_name = str(m_name) + ".gdb"
out_gdb = os.path.join(out_workspace, out_name)
if not arcpy.Exists(out_gdb):
    arcpy.CreateFileGDB_management(out_workspace, out_name)

#Print messages
arcpy.AddMessage('AoI: ' + AoI)
arcpy.AddMessage('Simulation Year: ' + str(simyear))
arcpy.AddMessage('Simulation Duration: ' + str(simduration))
arcpy.AddMessage('Input Directory: ' + in_workspace)
arcpy.AddMessage('Output Directory: ' + out_workspace)
arcpy.AddMessage("Starting processing...")

##############################################################################   
#Step 2. Read in relevant features to intersect with AoI
cvp_input = os.path.join(source_gdb, 'CVP') 
ehsit_input = os.path.join(source_gdb, 'ehsit')
bggenexs_input = os.path.join(source_gdb, 'bggenexs') 
bggensit_input = os.path.join(source_gdb, 'bggensit')

cvp_lyr = arcpy.MakeFeatureLayer_management(cvp_input, "cvp_lyr")
ehsit_lyr = arcpy.MakeFeatureLayer_management(ehsit_input, "ehsit_lyr")
bggenexs_lyr = arcpy.MakeFeatureLayer_management(bggenexs_input, "bggenexs_lyr")
bggensit_lyr = arcpy.MakeFeatureLayer_management(bggensit_input, "bggensit_lyr")

##############################################################################   
#Step 3. Select sites within model domain & compile list of Site IDs
AoI_lyr = arcpy.MakeFeatureLayer_management(AoI, "AoI_lyr")
# Features that undergo succession
succession_layers = [cvp_lyr,bggenexs_lyr,bggensit_lyr,ehsit_lyr]

# Fields containing site_ID
SiteID_fields = ['wids_sitec','SITE_NUM','FACIL_NAME','FACIL_NAME']

# List of selected Site IDs for AoI
SiteID_AoI = []

for index, lyr in enumerate(succession_layers):
    selection = arcpy.SelectLayerByLocation_management(in_layer=lyr,
                                       overlap_type="INTERSECT",
                                       select_features=AoI_lyr)
    # Search cursor to find Site_IDs
    with arcpy.da.SearchCursor(selection, SiteID_fields[index]) as rows:
        # Iterate through the rows in the cursor and compile the Site_IDs to a list
        count = 0
        for row in rows:
#            print row[0]            
            SiteID_AoI.append(row[0]) #row.getValue(SiteID_fields[index]))
            count = count + 1
    arcpy.AddMessage('Number of waste sites in {0}: {1}'.format(lyr, count)) #count should be:CVP = 45, ehsit = 345, bggenexs = 117, bggensit = 507
arcpy.AddMessage('Total number of waste sites in model domain: {0}'.format(len(SiteID_AoI))) #should be 1014

##############################################################################
#Step 4. Lookup list of YoI for selected sites
# Read in dictionary of waste sites w/ their YoI
in_YoI= csv.reader(open(os.path.join(working_dir, 'Script','YoI_Dictionary_FINAL.csv')), delimiter='\t')
YoI_Dict = {}
for row in in_YoI:
    YoI_Dict[row[0]] = [x for x in row[1:] if x != '']

# List of YoI for AoI
YoI_AoI = []

# Loop through YoI dictionary and pull out years for waste sites that are in YoI dictionary
for ID in SiteID_AoI:
    if ID in YoI_Dict:
        yrs = YoI_Dict[ID] 
        for y in yrs:
            YoI_AoI.append(y)
YoI_AoI_Unique = sorted(set(YoI_AoI))

##############################################################################
#Step 5. Filter out any YoI outside of the simulation period
# Calculate simulation end year
simend = simyear + simduration
arcpy.AddMessage('Simulation End Year: {0}'.format(simend))

# Loop through YoI_AoI list and kick out any values not in simulation period
YoI_AoI_Final = []
for y in YoI_AoI_Unique:
    if int(y) >= simyear and int(y) <= simend:
        YoI_AoI_Final.append(y)
arcpy.AddMessage('Years of Interest for model domain & simulation period: {0}'.format(YoI_AoI_Final))
arcpy.AddMessage('Total number of Years of Interest: {0}'.format(len(YoI_AoI_Final))) #should be 1014

##############################################################################
#Step 6. Clip RET outputs for YoI to the model domain and save to output folder
# Loop though YoI for AoI
for y in YoI_AoI_Final:
    # Open Recharge Estimates for YoI
    in_name = y + ".gdb"
    y_name = "RechargeEstimates_" + y
    in_gdb = os.path.join(in_workspace,in_name,y_name)
    arcpy.AddMessage('Evaluating year: {0}'.format(y))
    Recharge_lyr = arcpy.MakeFeatureLayer_management(in_gdb, "Recharge_lyr")
    #Set output file name
    oname ='Recharge_' + y
    Output_lyr = os.path.join(out_gdb,oname)
    # Clip Recharge Estimate polygon by model domain & Save to output folder
    clip = arcpy.Clip_analysis(Recharge_lyr,AoI_lyr,Output_lyr)
    

