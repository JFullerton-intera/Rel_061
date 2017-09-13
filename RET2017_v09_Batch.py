'''----------------------------------------------------------------------------------
 Tool Name:   Recharge Estimation Tool for Hanford Composite Analysis
 Source Name: RET2017_v09.py
 Version:     ArcGIS 10.3
 Author:      INTERA Inc.
 Required Arguments:
              Seven feature classes:
                  Soil Features
                  BRMP Cover Type
                  AAC 1943 Cover Type
                  NAIP 2011 Cover Type
                  Cleanup Verification Package
                  Environmental Hazardous Waste Sites
                  Existing Buildings
                  Existing Sites
              Four Tables:
                  Recharge Lookup
                  Disposition
                  Disposition lookup
              One directory:
                  Output
 Description: Calculates spatio-temporal recharge for the Hanford site in support of STOMP modeling for
              Composite Analysis. Outputs are site-wide shapefiles for each year of interest.
----------------------------------------------------------------------------------'''

# Import modules
import os
import arcpy #, sys
#import numpy as np
# from arcpy import env
from arcpy import mapping as mp
from datetime import datetime

#Allow for overwriting of outputs
arcpy.env.overwriteOutput = True

#Get working directory
working_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

########### INPUTS ######################################################
# Year of Interest
# in_YoI = list(range(1940,2100))
in_YoI = [1943,1944]     #   For testing/debugging reasons
# Output directory
out_workspace = r'C:\cygwin64\home\JFullerton\Intera\PSC-CHPRC\C003.HANOFF\Rel.61\Outputs\out_jbf' #JBP
#Features
in_workspace =  os.path.join(working_dir, 'Inputs', 'RET_InputDatabase_v4.gdb') #r'S:\PSC\CHPRC.C003.HANOFF\Rel.061\vadose\RET\Inputs\RET_InputDatabase_v3.gdb'
SoilFeatures = os.path.join(in_workspace, 'Soils') # Soil Features
brmp_input = os.path.join(in_workspace, 'BRMP') # BRMP Cover Type
aac_1943_input = os.path.join(in_workspace, 'AAC1943') # AAC 1943 Cover Type
naip_2011_input =os.path.join(in_workspace, 'NAIP2011') # 2011 NAIP
cvp_input = os.path.join(in_workspace, 'CVP') # Cleanup Verification Package
ehsit_input = os.path.join(in_workspace, 'ehsit') # Environmental Hazardous Waste Site
bggenexs_input = os.path.join(in_workspace, 'bggenexs') # Existing Buildings
bggensit_input = os.path.join(in_workspace, 'bggensit') # Existing SItes
#Tables
disposition_input = os.path.join(in_workspace, 'Disposition') # Disposition Table
lookup_input = os.path.join(in_workspace, 'DispositionLookup') # Disposition Lookup Table
RechargeLookup = os.path.join(in_workspace, 'RechargeLookup') # Recharge Lookup Table

######### CREATE LOG FILE ##############################################
# Create log file
# log = os.path.join(out_workspace,"RET_log_HC.txt")
# logfile = open(log, "w")
start = datetime.now()
# logfile.write('starttime' + str(start)+ '\n')
# logfile.write("qry_year: " + qry_year + '\n')

########### FUNCTIONS ######################################################
def setLookupDicts(disposition_lookup):
    dispositionLookup = arcpy.MakeTableView_management(disposition_lookup, 'dispositionLookup')
    # Calculate surface condition from disposition via cover type
    with arcpy.da.SearchCursor(dispositionLookup, ["Disposition", "Cover_Type", "SurfCond"]) as rows:
        for row in rows:
            coverDict[row[0]] = row[1]
            surfCondDict[row[0]] = row[2]

def DeleteSurfconAndCoverType(featureClass):
    fieldNames = [x.name for x in arcpy.ListFields(featureClass)]

    if 'SurfCon' in fieldNames:
        arcpy.DeleteField_management(featureClass, 'SurfCon')

    if 'Cover_Type' in fieldNames:
        arcpy.DeleteField_management(featureClass, 'Cover_Type')

    if 'Cover' in fieldNames:
        arcpy.DeleteField_management(featureClass, 'Cover')

def AddSource(featureClass, sourceExpression):
    """Adds Source Field to feature class"""
    Source = "Source" #'Source'
    arcpy.AddField_management (featureClass, Source, "TEXT")
    arcpy.CalculateField_management(featureClass,Source, sourceExpression, "PYTHON_9.3")

###############################TODO##########################Remove Calculate Succession from the RET Calculation ####
def CalculateSuccession(condition, beginDate):
#    modelYear = modelYear
    if modelYear < int(beginDate) + 5 or condition == r'default':
        return condition

    successionStage = 0
    if condition == 'Bare':
        successionStage = 0
    elif condition == 'Cheatgrass':
        successionStage = 5
    elif condition == 'Developing':
        successionStage = 10
    elif condition == 'Mature':
        successionStage = 40

    successionDuration = modelYear - beginDate
    successionStage +=  successionDuration

    if successionStage < 5:
        result = 'Bare'
    elif successionStage < 10:
        result = 'Cheatgrass'
    elif successionStage < 40:
        result = 'Developing'
    elif successionStage >= 40:
        result = 'Mature'
    else:
        result = 'FLAG'

    return result

def AddTextField(featureClass, fieldName, length):
    # Adds a text field to the feature class
    arcpy.AddField_management(featureClass, fieldName, "TEXT", field_length=length)


def AddSurfconAndCover(featureClass):
    # Adds two fields needed for update
    AddTextField(featureClass, 'SurfCond', 100)
    AddTextField(featureClass, 'CoverType', 100)

def FeatureSuccessionForCVP(features, opYearField = 'cvpYear' ):
    SurfCond = 'SurfCond'
#    Cover = 'CoverType'

    StartDisposition = "StartDisp"
    arcpy.AddField_management (features,  StartDisposition, "TEXT", field_length = 75)

    LastKnownCondition = "LastKnownCond"
    arcpy.AddField_management (features,  LastKnownCondition, "TEXT", field_length = 75)

    #Calculate Last Known Condition
    lastKnownField =  "LastKnownCond"
    opCondExpression = "!{0}!".format(SurfCond) #"[{0}]".format(SurfCond)

    arcpy.CalculateField_management(features, lastKnownField, opCondExpression, "PYTHON_9.3")

    surfCondValues = []
    coverValues = []
    startCond = []
    
    with arcpy.da.SearchCursor(features, [lastKnownField, opYearField]) as rows:
        for row in rows:
            lastKnown = row[0].strip()
            if lastKnown in surfCondDict:
                curSurfCond = surfCondDict[lastKnown]
                curCover = coverDict[lastKnown]
            elif lastKnown == '':
                curSurfCond = surfCondDict["default"]
                curCover = coverDict["default"]
            else:
                curSurfCond = 'undefined'
                curCover = 'undefined'
                
            if int(row[1]) == 98:
                startYear = '1998'
            elif int(row[1]) == 99:
                startYear = '1999'
            else:
                startYear = row[1]
                
            startCond.append(curSurfCond)            
            
            resultCondition = CalculateSuccession(curSurfCond, int(startYear))
            coverValues.append(curCover)
            surfCondValues.append(resultCondition)

    surfConField = 'SurfCond'
    coverField = 'CoverType'
    lastKnownField =  "LastKnownCond"
    startDispField =  "StartDisp"

    with arcpy.da.UpdateCursor(features, [lastKnownField, surfConField, coverField, startDispField ]) as rows:
        x = 0
        for row in rows:
            row[1] = surfCondValues[x]
            row[2] = coverValues[x]
            row[3] = startCond[x]

            rows.updateRow(row)
            x += 1
    return

# def FeatureSuccession(features, startYear = 2010 ):
#     SurfCond = 'SurfCond'
# #    Cover = 'CoverType'
#
#     LastKnownCondition = "LastKnownCond"
#     arcpy.AddField_management (features,  LastKnownCondition, "TEXT", field_length = 75)
#
#     #Calculate Last Known Condition
#     lastKnownField =  "LastKnownCond"
#     opCondExpression = "!{0}!".format(SurfCond) #"[{0}]".format(SurfCond)
#
#     arcpy.CalculateField_management(features, lastKnownField, opCondExpression, "PYTHON_9.3")
#
#     surfCondValues = []
#     coverValues = []
#     startCond = []
#     with arcpy.da.SearchCursor(features, [lastKnownField]) as rows:
#         for row in rows:
#             lastKnown = row[0].strip()
#             if lastKnown in surfCondDict:
#                 curSurfCond = surfCondDict[lastKnown]
#                 curCover = coverDict[lastKnown]
#             elif lastKnown == '':
#                 curSurfCond = surfCondDict["default"]
#                 curCover = coverDict["default"]
#             else:
#                 curSurfCond = 'undefined'
#                 curCover = 'undefined'
#
#             startCond.append(curSurfCond)
#
#             resultCondition = CalculateSuccession(curSurfCond, startYear)
#             coverValues.append(curCover)
#             surfCondValues.append(resultCondition)
#
#     surfConField = 'SurfCond'
#     coverField = 'CoverType'
#     lastKnownField =  "LastKnownCond"
#
#     with arcpy.da.UpdateCursor(features, [lastKnownField, surfConField, coverField ]) as rows:
#         x = 0
#         for row in rows:
#             row[1] = surfCondValues[x]
#             row[2] = coverValues[x]
#
#             rows.updateRow(row)
#             x += 1
#     return

def Build_BRMP(interim_dir, BRMP_input, recharge_lookup):
    # Final Fields
    Source = "Source"#'Source'
#    SurfCond = 'SurfCond'
    Cover = "CoverType" #'CoverType'

    BRMP_temp = arcpy.CopyFeatures_management(BRMP_input, os.path.join(interim_dir, 'BRMP_'+yearString))

    AddSurfconAndCover(BRMP_temp)
    arcpy.AddField_management (BRMP_temp, Source, "TEXT")

    expression = '"BRMP_2011"' #''' "BRMP_2011" '''
    arcpy.CalculateField_management(BRMP_temp,Source, expression,"PYTHON_9.3")

    CoverExpression = "changeBRMPIndValue(!Cover_Type!)"#'''changeBRMPIndValue(!Cover_Type!) '''

    cover_codeblock =  """
def changeBRMPIndValue(brmp):
    if brmp == r"Gravel/Industrial/Non-Vegetated/Agricultural/Exotic Weed":
        result = r"Gravel/Industrial/Non-Vegetated/Exotic Weed"
    elif brmp == r"Barrier-MinRchrg":
        result = r"Barrier/MinRchrg"
    else:
        result = brmp

    return result """

    arcpy.CalculateField_management(BRMP_temp,Cover, CoverExpression, "PYTHON_9.3", cover_codeblock)

    surfcon_lookup = recharge_lookup
    surfconLookup = arcpy.MakeTableView_management(surfcon_lookup,  'surfconLookup')

    # Calculate surface condition from disposition via cover type
    surfCondDict = {}
    with arcpy.da.SearchCursor(surfconLookup, ["Cover_Type", "SurfCond"]) as rows:
        for row in rows:
            surfCondDict[row[0]] = row[1]

    surfConField = 'SurfCond'
    coverField = 'CoverType'


    with arcpy.da.UpdateCursor(BRMP_temp, [ coverField, surfConField]) as rows:
        for row in rows:
            row[1] = surfCondDict[row[0]]
            rows.updateRow(row)

    DeleteSurfconAndCoverType(BRMP_temp)
    return BRMP_temp

def Build_AAC1943(interim_dir, aac_1943_input):
    #Final Fields
    Source = "Source" #'Source'
    SurfCond = "SurfCond"#'SurfCond'
    Cover = "CoverType"#'CoverType'

    aac_1943_temp = arcpy.CopyFeatures_management(aac_1943_input, os.path.join(interim_dir, 'AAC_1943_'+yearString))

    AddSurfconAndCover(aac_1943_temp)
    arcpy.AddField_management (aac_1943_temp, Source, "TEXT")

    expression = '"AAC_1943"'#''' "AAC_1943" '''
    arcpy.CalculateField_management(aac_1943_temp,Source, expression, "PYTHON_9.3")

    # Set Surfcon
    SurfConExpression = "get_siteid(!"+ 'SurfCon' +"!)"
    surfcon_codeblock =  """
def get_siteid(surfcon):
    if surfcon == 'Cheatgrass':
        result =  'Irrigated'
    else:
        result = surfcon
    return result"""
    arcpy.CalculateField_management(aac_1943_temp,SurfCond, SurfConExpression, "PYTHON_9.3", surfcon_codeblock)

    CoverExpression = "get_siteid(!"+ 'Cover' +"!)"
    cover_codeblock =  """
def get_siteid(Cover):
    if Cover == 'Abandoned Fields':
        result =  'Agricultural / Orchard'
    else:
        result = Cover
    return result"""
    arcpy.CalculateField_management(aac_1943_temp,Cover, CoverExpression, "PYTHON_9.3", cover_codeblock)

    DeleteSurfconAndCoverType(aac_1943_temp)
    return aac_1943_temp

def Build_Post_AAC1943(interim_dir, aac_1943_input):
    #Final Fields
    Source = "Source" #'Source'
    SurfCond = "SurfCond" #'SurfCond'
    Cover = "CoverType" #'CoverType'

    aac_1943_temp = arcpy.CopyFeatures_management(aac_1943_input, os.path.join(interim_dir, 'AAC_1943_'+yearString))

    AddSurfconAndCover(aac_1943_temp)
    arcpy.AddField_management (aac_1943_temp, Source, "TEXT")

    expression = '"AAC_1943"' #''' "NAIP_1943" '''
    arcpy.CalculateField_management(aac_1943_temp,Source, expression, "PYTHON_9.3")

    SurfConExpression = "!SurfCon!" #''' [SurfCon] '''
    arcpy.CalculateField_management(aac_1943_temp,SurfCond, SurfConExpression, "PYTHON_9.3")

    CoverExpression = "!Cover!" #''' [Cover] '''
    arcpy.CalculateField_management(aac_1943_temp,Cover, CoverExpression, "PYTHON_9.3")

    DeleteSurfconAndCoverType(aac_1943_temp)
    return aac_1943_temp

def Build_NAIP2011(interim_dir, NAIP_2011_input):
    #Final Fields
    Source = "Source" #Source'
    SurfCond = "SurfCond" #'SurfCond'
    Cover = "CoverType" #'CoverType'

    NAIP_2011_temp = arcpy.CopyFeatures_management(NAIP_2011_input, os.path.join(interim_dir, 'NAIP_2011_'+yearString))

    AddSurfconAndCover(NAIP_2011_temp)
    arcpy.AddField_management (NAIP_2011_temp, Source, "TEXT")

    expression = '"NAIP_2011"' #''' "AAC_2011" '''
    arcpy.CalculateField_management(NAIP_2011_temp,Source, expression, "PYTHON_9.3")

    SurfConExpression = "!SurfCon!" #''' [SurfCon]'''
    arcpy.CalculateField_management(NAIP_2011_temp,SurfCond, SurfConExpression, "PYTHON_9.3")

    CoverExpression = "!Cover!" #''' [Cover] '''
    arcpy.CalculateField_management(NAIP_2011_temp,Cover, CoverExpression, "PYTHON_9.3")

    DeleteSurfconAndCoverType(NAIP_2011_temp)
    return NAIP_2011_temp

def Build_CVP(interim_dir, CVP_input, qry_year):
    qry_year = modelYear
    # Does not work right now
    # Does not need to be joined to Marie's data
    # Final Fields
    # Source = 'Source'
    SurfCond = 'SurfCond'
    Cover = 'CoverType'

    # CVP Features
    # creates a copy of the original data to be used in processing
    temp_feats = arcpy.CopyFeatures_management(CVP_input, os.path.join(interim_dir, 'cvp_'+ yearString))

    # adds field cvp_year and enters the year value for each field
    cvpYearField = "cvp_year"
    arcpy.AddField_management(temp_feats,cvpYearField,"DOUBLE")
    expression = "get_year(!Key_WSRF!)"
    codeblock =  """
import re
def get_year(year):
    y = re.compile('^\d+')
    actual = y.match(year)
    if actual is not None:
        result_string = actual.group()
        result = int(result_string)
        return result
    else:
        return 00"""
    arcpy.CalculateField_management(temp_feats,cvpYearField, expression, "PYTHON_9.3", codeblock)

    # adds field year_valid and assigns "valid" or "not valid"
    yearValidField =  "year_valid"
    arcpy.AddField_management(temp_feats,yearValidField,"TEXT")
    expression = "is_year(!"+cvpYearField +"!)"
    valid_codeblock =  """
def is_year(year):
    year_num = int(year)
    if year_num >= 2000 and year_num <= {0}:
        return "valid"
    elif year_num >= 98 and year_num < 100:
        return "valid"
    else:
        return "not valid" """.format(qry_year)
    arcpy.CalculateField_management(temp_feats,yearValidField, expression, "PYTHON_9.3", valid_codeblock)

    # creates a layer from the temp features
    temp_cvp_layer = "temp_cvp_layer"
    arcpy.MakeFeatureLayer_management(temp_feats, temp_cvp_layer)

    # selects valid features from temp and copies them to "CVP_valid"
    arcpy.SelectLayerByAttribute_management(temp_cvp_layer,"NEW_SELECTION", ''' "year_valid" = 'valid' ''')
    CVP_valid = arcpy.CopyFeatures_management(temp_cvp_layer, os.path.join(interim_dir, 'CVP_valid'))

    #Add fields
    cvp_expression = '"cvp"'        #''' "cvp" '''
    AddSource(CVP_valid, cvp_expression)
    AddSurfconAndCover(CVP_valid)

    SurfConExpression = '"Developing"'  #''' "Developing" '''
    arcpy.CalculateField_management(CVP_valid,SurfCond, SurfConExpression, "PYTHON_9.3")

    CoverExpression = '"Artificial Regeneration"'   #''' "Artificial Regeneration" '''
    arcpy.CalculateField_management(CVP_valid,Cover, CoverExpression, "PYTHON_9.3")

    FeatureSuccessionForCVP(CVP_valid, cvpYearField)
    DeleteSurfconAndCoverType(CVP_valid)
    return CVP_valid

def Build_Ehsites(interim_dir, ehsit_input, disposition_input, disposition_lookup, brmpIsValid, brmp_temp):
    # ENVIRONMENTAL SITES
    # add wastesite table into map
    dispositionTable = mp.TableView(disposition_input)
    dispositionLookup = mp.TableView(disposition_lookup)
    ehsitBase = "ehsit_{0}.".format(yearString)

    # declare environmental hazardous sites as a map layer
    ehsit_temp = arcpy.CopyFeatures_management(ehsit_input, os.path.join(interim_dir, 'ehsit_' + yearString + '_temp'))
    ehsit_lyrName = 'ehsit_temp'
    ehsit = arcpy.MakeFeatureLayer_management(ehsit_temp, ehsit_lyrName)

    # delete poop site
    with arcpy.da.UpdateCursor(ehsit, ["HAZSITE_ID"]) as rows:
        for row in rows:
            if row[0] == 2732:
                rows.deleteRow()

    #***** add fields before joining (avoids naming dilemna) *****#
    ehsit_expression = '"ehsit"'    #''' "ehsit" '''
    AddSource(ehsit_temp, ehsit_expression)

    fields_to_add = {'TEXT': [['Site_ID', 25], ['SurfCond', 100], ['CoverType', 100], ['Status', 11]],
                     'LONG': ['Start_Ops', 'End_Ops', 'First_Action', 'Final_Action']}

    for field in fields_to_add['TEXT']:
        arcpy.AddField_management(ehsit_temp, field[0], "TEXT", field_length=field[1])
    for field in fields_to_add['LONG']:
        arcpy.AddField_management(ehsit_temp, field, "LONG")

    # declare key fields
    eh_NumField = "SITE_NUM"

    # Calculate SiteID
    eh_keyField = 'Site_ID'
    siteExpression = "get_siteid(!"+eh_NumField +"!)"
    siteid_codeblock =  """
def get_siteid(site):
    return site.split(';')[0] """
    arcpy.CalculateField_management(ehsit_temp,eh_keyField, siteExpression, "PYTHON_9.3", siteid_codeblock)

    # Intersect ehsit with BRMP
    brmp_union = brmp_input
    outdir = os.path.join(arcpy.Describe(ehsit_temp).path, ehsitBase.replace('.', ''))
    ehsit_temp = arcpy.Intersect_analysis([ehsit_temp, brmp_union], outdir, 'ALL')
    ehsit = arcpy.MakeFeatureLayer_management(ehsit_temp, ehsitBase.replace('.', ''))

    # Join ehsites to disposition table
    disposition_keyField = 'Site_ID'
    arcpy.AddJoin_management(ehsit,eh_keyField,dispositionTable,disposition_keyField)

    # Calculate Start_Ops, End_Ops, Disposition, Future Disposition
    dispDate = 'Date_Disposition'       # 'Disposition$.Date_Disposition' #GLT
    begDate = 'Date_Begin'              # 'Disposition$.Date_Begin' #JBF
    endDate = 'Date_End'                # 'Disposition$.Date_End' #JBF
    futureDate = 'Disposition_TPA_Date' # 'Disposition$.Disposition_TPA_Date' #GLT

    # opYearExpression = "get_opYear(!{0}!,!{1}!)".format(futureDate, dispDate)
    opYear_codeblock = """
def get_opYear(date_field,default):
    if date_field is None:
        opYear = default
    elif date_field:
        opYear = int(date_field)
    else:
        opYear = default
    return opYear """
    opYearExpression = "get_opYear(!{0}!,None)".format(begDate)
    opYearField = [ehsitBase + fields_to_add['LONG'][0]]
    arcpy.CalculateField_management(ehsit, opYearField[-1], opYearExpression, "PYTHON_9.3", opYear_codeblock)
    opYearExpression = "get_opYear(!{0}!,None)".format(endDate)
    opYearField += [ehsitBase + fields_to_add['LONG'][1]]
    arcpy.CalculateField_management(ehsit, opYearField[-1], opYearExpression, "PYTHON_9.3", opYear_codeblock)
    opYearExpression = "get_opYear(!{0}!,None)".format(dispDate)
    opYearField += [ehsitBase + fields_to_add['LONG'][2]]
    arcpy.CalculateField_management(ehsit, opYearField[-1], opYearExpression, "PYTHON_9.3", opYear_codeblock)
    opYearExpression = "get_opYear(!{0}!,2042)".format(futureDate)
    opYearField += [ehsitBase + fields_to_add['LONG'][3]]
    arcpy.CalculateField_management(ehsit, opYearField[-1], opYearExpression, "PYTHON_9.3", opYear_codeblock)

    #***** Calculate the appropriate condition *****#
    # The first step of this is to determine which disposition is correct for the modelYear in question for each site.
    # Perform a loop to evaluate which state the waste site is currently in and flag where values are NULL
    # Options for the site status are the following:
    #       Nonexistent = Has not yet come into existence, has not accepted waste according to historical data
    #       Active = Either begun to accept waste or has been disturbed by construction
    #       Inactive = The waste site exists but no longer accepts waste, will regrow vegetation
    #       Intermediate = The waste site is between inactivity and full closure
    #       Final = All planned/active remediation efforts have been concluded
    #       FLAG = There is some error that needs to be addressed, most likely a missing year

    status = ehsitBase + 'Status'
    opCondExpression = "get_opCond({0},!{1}!,!{2}!,!{3}!,!{4}!)".format(modelYear,
                                                                        ehsitBase + fields_to_add['LONG'][0],
                                                                        ehsitBase + fields_to_add['LONG'][1],
                                                                        ehsitBase + fields_to_add['LONG'][2],
                                                                        ehsitBase + fields_to_add['LONG'][3])

    opCond_codeblock =  """
def get_opCond(modelYear,startOps,endOps,currDisp,finDisp):
    opCond = "FLAG"
    if startOps is not None:
        if modelYear < startOps:
            opCond = "NONEXISTENT"
        elif endOps is not None:
            if modelYear >= startOps and modelYear <= endOps:
                opCond = "ACTIVE"
            elif currDisp is not None:
                if modelYear > endOps and modelYear < currDisp:
                    opCond = "INACTIVE"
                elif finDisp is not None:
                    if modelYear >= currDisp and modelYear < finDisp:
                        opCond = "INTERMEDIATE"
                    elif modelYear >= finDisp:
                        opCond = "FINAL"
    elif endOps is not None and currDisp is not None:
        if modelYear > endOps and modelYear < currDisp:
            opCond = "INACTIVE"
        elif finDisp is not None:
            if modelYear >= currDisp and modelYear < finDisp:
                opCond = "INTERMEDIATE"
            elif modelYear >= finDisp:
                opCond = "FINAL"
    elif currDisp is not None and finDisp is not None:
        if modelYear >= currDisp and modelYear < finDisp:
            opCond = "INTERMEDIATE"
        elif modelYear >= finDisp:
            opCond = "FINAL"
    elif finDisp is not None:
        if modelYear >= finDisp:
            opCond = "FINAL"
    return opCond """
    arcpy.CalculateField_management(ehsit, status, opCondExpression, "PYTHON_9.3", opCond_codeblock)

    # Create dictionary using ehsit_[year] and BRMP_[year] to assign to each waste site a cover type and condition
    # The psuedo method for this is:
    #   Union(ehsit_[year],BRMP_[year],output) --> Summary Statistics(Sum of Area(s) by Site Number)
    #   Create Python Dictionary for each waste site that contains in detail the vegetation that makes up each site
    # Will only be performed if the BRMP shapefile is valid (valid years defined in earlier section of code)
    if brmpIsValid and 'ehsit_brmp_dict' not in globals():
        outdir = os.path.join(out_gdb, 'ehsit_brmp_union_{0}'.format(yearString))
        ehsit_brmp_union = arcpy.Union_analysis([ehsit, brmp_temp], outdir, join_attributes="ALL")

        # Create dictionary of the ehsit_brmp_table if it does not exist
        fields = [ehsitBase.replace('.','') + '_Site_ID',   # row[0]
                  'FID_BRMP_{0}'.format(yearString),        # row[1]
                  'SurfCond',                               # row[2]
                  'CoverType']                              # row[3]
        global ehsit_brmp_dict
        ehsit_brmp_dict = {}
        with arcpy.da.SearchCursor(ehsit_brmp_union, fields) as rows:
            count = 0
            for row in rows:
                count += 1
                if row[0] is None:
                    pass
                elif row[0] == '':
                    pass
                elif row[0] == ' ':
                    pass
                elif str(str(row[0]) + '_' + str(row[1])) not in ehsit_brmp_dict:
                    siteID = str(str(row[0]) + '_' + str(row[1]))
                    ehsit_brmp_dict[siteID] = {'SurfCond': row[2], 'CoverType':row[3]}
                else:
                    pass

    # Calculate surface condition based on vegetation succession
    inter_disp = 'Disposition.Actual_Disposition'   # 'Disposition$.Actual_Disposition' #JBF
    future_disp = 'Disposition.TPA_Disposition'     # 'Disposition$.TPA_Disposition' #JBF

    cur_year = {}
    fields = [status,                                   # row[0]
              'ehsit_{0}.Site_ID'.format(yearString),   # row[1]
              ehsitBase + 'FID_BRMP',                   # row[2]
              inter_disp,                               # row[3]
              future_disp,                              # row[4]
              ]

    with arcpy.da.SearchCursor(ehsit, fields)as rows:
        for row in rows:
            disposition = row[0].strip()
            id = str(str(row[1]) + '_' + str(row[2]))
            # Check that the current year being calculated is the first. If the first, then apply BRMP SurfConds to all
            # sites. ***IMPORTANT*** The year range must start with an earlier year than the first waste site startOps
            # date. The first known startOps date currently is 1944
            if int(yearString) == in_YoI[0]:
                cur_year[id] = {'SurfCond': ehsit_brmp_dict[id]['SurfCond'],
                                    'CoverType': ehsit_brmp_dict[id]['CoverType']}
            # If Nonexistent, apply SurfConds from BRMP shapefile as natural vegetation/background state
            elif disposition.lower() == 'nonexistent':
                cur_year[id] = {'SurfCond': ehsit_brmp_dict[id]['SurfCond'],
                                'CoverType': ehsit_brmp_dict[id]['CoverType']}
            # If Active, use 'Bare-Disturbed' conditions
            elif disposition.lower() == 'active' or disposition.lower() == 'inactive':
                cur_year[id] = {'SurfCond': 'Bare', 'CoverType': 'Disturbed'}
            elif disposition.lower() == 'intermediate':
                if row[3] is not None:
                    with arcpy.da.SearchCursor(dispositionLookup, ['Disposition', 'Cover_Type', 'SurfCond']) as table:
                        for search in table:
                            if row[3] == search[0]:
                                cur_year[id] = {'SurfCond': search[2], 'CoverType': search[1]}
                                break
                else:
                    cur_year[id] = {'SurfCond': prev_year[id]['SurfCond'],
                                        'CoverType': prev_year[id]['CoverType']}
            elif disposition.lower() == 'final':
                if row[4] is not None:
                    with arcpy.da.SearchCursor(dispositionLookup, ['Disposition', 'Cover_Type', 'SurfCond']) as table:
                        for search in table:
                            if row[4] == search[0]:
                                cur_year[id] = {'SurfCond': search[2], 'CoverType': search[1]}
                                break
                else:
                    cur_year[id] = {'SurfCond': prev_year[id]['SurfCond'],
                                        'CoverType': prev_year[id]['CoverType']}
            else:
                cur_year[id] = {'SurfCond': prev_year[id]['SurfCond'],
                                    'CoverType': prev_year[id]['CoverType']}

    #remove joins
    arcpy.RemoveJoin_management(ehsit)

    surfConField = 'SurfCond'
    coverTypeField = 'CoverType'

    if 'prev_year' not in globals():
        global prev_year
        prev_year = {}
    else:
        prev_year = {}

    with arcpy.da.UpdateCursor(ehsit, ['Site_ID', 'FID_BRMP', surfConField, coverTypeField]) as rows:
        x = 0
        for row in rows:
            id = str(str(row[0]) + '_' + str(row[1]))
            prev_year[id] = cur_year[id]
            row[2] = cur_year[id]['SurfCond']
            row[3] = cur_year[id]['CoverType']

            rows.updateRow(row)
            x += 1

    return ehsit

def Build_Bggenexs(interim_dir, bggenexs_input, disposition_input):
    # BUILDINGS

    #Final Fields
#    Source = 'Source'
    SurfCond = 'SurfCond'
#    Cover = 'CoverType'

    dispositionTable = mp.TableView(disposition_input)
    bggenexs_temp = arcpy.CopyFeatures_management(bggenexs_input, os.path.join(interim_dir, 'bggenexs_' + yearString))

    # Make building layers
    bggenexs = arcpy.MakeFeatureLayer_management(bggenexs_temp, 'bggenexs_lyr')

    bggenexs_expression = '"bggenexs"' #''' "bggenexs" '''

    #Add fields
    AddSource(bggenexs_temp, bggenexs_expression)
    AddSurfconAndCover(bggenexs_temp)

    #barrierExpression = '"bar"' #''' "bar" ''' #JBP
    #arcpy.CalculateField_management(bggenexs_temp,SurfCond, barrierExpression, "PYTHON_9.3") #JBP

    building_key = "FACIL_NAME"
    disposition_keyField = 'Site_ID'

    # add fields before joining (avoids naming dilemna)
    SuccessionBegin = 'SuccessionBegin'
    arcpy.AddField_management (bggenexs_temp, SuccessionBegin, "LONG")

    LastKnownCondition = "LastKnownCond"
    arcpy.AddField_management (bggenexs_temp,  LastKnownCondition, "TEXT", field_length = 75)

    StartDisposition = "StartDisp"
    arcpy.AddField_management (bggenexs_temp,  StartDisposition, "TEXT", field_length = 75)
    
    # Calculate Operating Year
    bggenexsBase = "bggenexs_{0}.".format(yearString)
    opYearField = bggenexsBase + SuccessionBegin    
    
    futureDate = 'Disposition_TPA_Date' #'Disposition$.Disposition_TPA_Date' #GLT
    # dispDate = 'Date_Disposition' #'Disposition$.Date_Disposition' #GLT
    begDate = 'Date_Begin'
    curDisp = 'Disposition' #'Disposition$.Disposition' #GLT

    # Add join for buildings
    arcpy.AddJoin_management(bggenexs,building_key,dispositionTable,disposition_keyField)

    # Calculate disposition date
    # opYearExpression = "get_opYear(!{0}!,!{1}!)".format(futureDate, dispDate)
    opYearExpression = "get_opYear(!{0}!,!{1}!)".format(futureDate, begDate)
    opYear_codeblock =  """
def get_opYear(future_year, date_field):
    if date_field is None:
        opYear = 1944
    elif date_field:
        opYear = int(date_field)
    else:
        opYear = 1944
    return opYear """
    arcpy.CalculateField_management(bggenexs,opYearField, opYearExpression, "PYTHON_9.3", opYear_codeblock)
    
    #Calculate Last Known Condition
    bggenexsBase = "bggenexs_{0}.".format(yearString)
    lastKnownField = bggenexsBase + "LastKnownCond"
    opCondExpression = "get_opCond(!{0}!)".format(curDisp)
    opCond_codeblock =  """
def get_opCond(disposition_cond):
    if disposition_cond is not None:
        opCond = disposition_cond
    else:
        opCond = "default"

    return opCond """
    arcpy.CalculateField_management(bggenexs, lastKnownField, opCondExpression, "PYTHON_9.3", opCond_codeblock)

    # define deriveCondition Function
    # Calculate surface condition based on vegetation succession

    surfCondValues = []
    coverValues = []
    startCond = []

    with arcpy.da.SearchCursor(bggenexs, [lastKnownField, opYearField]) as rows:
        for row in rows:
            lastKnown = row[0].strip()
            if lastKnown in surfCondDict:
                curSurfCond = surfCondDict[lastKnown]
                curCover = coverDict[lastKnown]
            elif lastKnown == '':
                curSurfCond = surfCondDict["default"]
                curCover = coverDict["default"]
            else:
                curSurfCond = 'undefined'
                curCover = 'undefined'

            startYear = row[1]
            startCond.append(curSurfCond)            
            
            # Set features to default if before disposition date
            if modelYear < startYear:
                curSurfCond = r'default'
                curCover = r'default'
                
            resultCondition = CalculateSuccession(curSurfCond, startYear)
            coverValues.append(curCover)
            surfCondValues.append(resultCondition)

    #remove joins
    arcpy.RemoveJoin_management(bggenexs)

    surfConField = 'SurfCond'
    coverField = 'CoverType'
    lastKnownField =  "LastKnownCond"
    startDispField =  "StartDisp"

    with arcpy.da.UpdateCursor(bggenexs, [lastKnownField, surfConField, coverField, startDispField ]) as rows:
        x = 0
        for row in rows:
            row[1] = surfCondValues[x]
            row[2] = coverValues[x]
            row[3] = startCond[x]

            rows.updateRow(row)
            x += 1

    DeleteSurfconAndCoverType(bggenexs)
    return bggenexs

def Build_Bggensit(interim_dir, bggensit_input, disposition_input):
    # BUILDINGS

    #Final Fields
#    Source = 'Source'
    SurfCond = 'SurfCond'
#    Cover = 'CoverType'

    dispositionTable = mp.TableView(disposition_input)
    bggensit_temp = arcpy.CopyFeatures_management(bggensit_input, os.path.join(interim_dir, 'bggensit_' + yearString))

    # Make building layers
    bggensit = arcpy.MakeFeatureLayer_management(bggensit_temp, 'bggensit_lyr')

    bggensit_expression = '"bggensit"' #''' "bggensit" '''

    #Add fields
    AddSource(bggensit_temp, bggensit_expression)
    AddSurfconAndCover(bggensit_temp)

    #barrierExpression = '"bar"' #''' "bar" ''' #JBP
    #arcpy.CalculateField_management(bggensit_temp,SurfCond, barrierExpression, "PYTHON_9.3") #JBP

    building_key = "FACIL_NAME"
    disposition_keyField = 'Site_ID'

    # add fields before joining (avoids naming dilemna)
    SuccessionBegin = 'SuccessionBegin'
    arcpy.AddField_management (bggensit_temp, SuccessionBegin, "LONG")

    LastKnownCondition = "LastKnownCond"
    arcpy.AddField_management (bggensit_temp,  LastKnownCondition, "TEXT", field_length = 75)

    StartDisposition = "StartDisp"
    arcpy.AddField_management (bggensit_temp,  StartDisposition, "TEXT", field_length = 75)
    
    # Calculate Operating Year
    bggensitBase = "bggensit_{0}.".format(yearString)
    opYearField = bggensitBase + SuccessionBegin    
    
    futureDate = 'Disposition_TPA_Date' #'Disposition$.Disposition_TPA_Date' #GLT
    dispDate = 'Date_Disposition' #'Disposition$.Date_Disposition' #GLT
    curDisp = 'Disposition' #'Disposition$.Disposition' #GLT

    # Add join for buildings
    arcpy.AddJoin_management(bggensit,building_key,dispositionTable,disposition_keyField)

    # Calculate disposition date
    opYearExpression = "get_opYear(!{0}!,!{1}!)".format(futureDate, dispDate)
    opYear_codeblock = """
def get_opYear(future_year, date_field):
    if date_field is None:
        opYear = 1944
    elif date_field:
        opYear = int(date_field)
    else:
        opYear = 1944
    return opYear """
    arcpy.CalculateField_management(bggensit,opYearField, opYearExpression, "PYTHON_9.3", opYear_codeblock)
    
    #Calculate Last Known Condition
    bggensitBase = "bggensit_{0}.".format(yearString)
    lastKnownField = bggensitBase + "LastKnownCond"
    opCondExpression = "get_opCond(!{0}!)".format(curDisp)
    opCond_codeblock =  """
def get_opCond(disposition_cond):
    if disposition_cond is not None:
        opCond = disposition_cond
    else:
        opCond = "default"

    return opCond """
    arcpy.CalculateField_management(bggensit, lastKnownField, opCondExpression, "PYTHON_9.3", opCond_codeblock)

    # define deriveCondition Function
     # Calculate surface condition based on vegetation succession

    surfCondValues = []
    coverValues = []
    startCond = []

    with arcpy.da.SearchCursor(bggensit, [lastKnownField, opYearField]) as rows:
        for row in rows:
            lastKnown = row[0].strip()
            if lastKnown in surfCondDict:
                curSurfCond = surfCondDict[lastKnown]
                curCover = coverDict[lastKnown]
            elif lastKnown == '':
                curSurfCond = surfCondDict["default"]
                curCover = coverDict["default"]
            else:
                curSurfCond = 'undefined'
                curCover = 'undefined'

            startYear = row[1]
            startCond.append(curSurfCond)            
            
            # Set features to default if before disposition date
            if modelYear < startYear:
                curSurfCond = r'default'
                curCover = r'default'
                
            resultCondition = CalculateSuccession(curSurfCond, startYear)
            coverValues.append(curCover)
            surfCondValues.append(resultCondition)

    #remove joins
    arcpy.RemoveJoin_management(bggensit)

    surfConField = 'SurfCond'
    coverField = 'CoverType'
    lastKnownField =  "LastKnownCond"
    startDispField =  "StartDisp"

    with arcpy.da.UpdateCursor(bggensit, [lastKnownField, surfConField, coverField, startDispField ]) as rows:
        x = 0
        for row in rows:
            row[1] = surfCondValues[x]
            row[2] = coverValues[x]
            row[3] = startCond[x]

            rows.updateRow(row)
            x += 1

    DeleteSurfconAndCoverType(bggensit)
    return bggensit

def Build_RechargeFeatures(interim_dir, UpdatedFeatures, SoilFeatures, lookup_input ):

    Soil_temp = arcpy.CopyFeatures_management(SoilFeatures, os.path.join(interim_dir, 'Soil_temp'))
    Recharge_path = os.path.join(interim_dir, "RechargeEstimates_" + yearString)
    recharge_feats = arcpy.Union_analysis([UpdatedFeatures, Soil_temp], Recharge_path)

#    rateWorksheet = "SurfCondRecharge$"
    rateLookupPath = lookup_input #os.path.join(lookup_input, rateWorksheet)   #GLT

    rateTable = arcpy.MakeTableView_management(rateLookupPath, 'rateTable')
    rateFields = ['Cover_Type', 'SurfCond', 'Qy', 'Ri', 'Rp', 'He', 'Kf', 'Ba', 'El', 'Ls', 'Eb', 'Ki', 'Wa', 'Sc', 'P', 'Qu', 'Rv', 'D', 'XX']

    rechargeField = "RechargeRate"
    arcpy.AddField_management(recharge_feats, rechargeField, "DOUBLE" )

    rateDict = {}
    with arcpy.da.SearchCursor(rateTable,rateFields) as rows:
        for row in rows:
            cover = row[0]
            surfaceCondition = row[1]
            for x in range(2, len(rateFields)):
                soilType = rateFields[x]
                rateDict[(cover, surfaceCondition, soilType)] = row[x]

    resultFields = ['CoverType', 'SurfCond', 'TEXT_SYM', rechargeField]
    with arcpy.da.UpdateCursor(recharge_feats,resultFields) as rows:
        for row in rows:
            cover = row[0]
            surfaceCondition = row[1]
            soilType = row[2]
            key = (cover, surfaceCondition, soilType)
            if key in rateDict:
                row[3] = float(rateDict[key])
            else:
                row[3] = -9999
            rows.updateRow(row)
    return recharge_feats

def DeleteExcessRechargeFeatures(RechargeFeatures):
#    finalFields = ['SurfCond', 'CoverType', 'Source', 'TEXT_SYM', 'SOIL_NAME', 'RechargeRate']
    fieldNames = [x.name for x in arcpy.ListFields(RechargeFeatures)]
    for name in fieldNames:
        if name not in fieldNames:
            arcpy.DeleteField_management(featureClass, name)

def Bootleg_Update(input_layer, update_layer, output_feature_class, update_fields):
    interim_features = os.path.dirname(output_feature_class) + "\\" + "interim_features"

    # Union the input layer and update layer
    UnionFeatures = arcpy.Union_analysis(in_features=[input_layer, update_layer], out_feature_class=interim_features,
                        join_attributes='ALL',
                        cluster_tolerance='#',
                        gaps='GAPS')

    # Create in memory layer for input layer
    input_layer_result = arcpy.MakeFeatureLayer_management(input_layer, 'input_layer')
    input_layer_object = input_layer_result.getOutput(0)
    input_layer_path = input_layer_object.dataSource
    input_fc_name = os.path.basename(input_layer_path)

    # Create in memory layer for update layer
    update_layer_result = arcpy.MakeFeatureLayer_management(update_layer, 'update_layer')
    update_layer_object = update_layer_result.getOutput(0)
    update_layer_path = update_layer_object.dataSource
    update_fc_name = os.path.basename(update_layer_path)

    # Create in memory layer for union layer
    UnionLayer = "union_layer"
    arcpy.MakeFeatureLayer_management(UnionFeatures, UnionLayer)

    # Select all features that are not from the update feature
    arcpy.SelectLayerByAttribute_management(UnionLayer,"NEW_SELECTION", ''' "FID_{0}" <> -1 '''.format(update_fc_name))

    # Set update fields with overlapping feature values
    for field in update_fields:
        arcpy.CalculateField_management(UnionLayer, field, '!'+field+'_1!', "PYTHON_9.3")

    # Select all features that are from the update feature
    arcpy.SelectLayerByAttribute_management(UnionLayer,"NEW_SELECTION", ''' "FID_{0}" = -1 '''.format(update_fc_name))

    # Assign the Update FID with the negative of Input FID
    arcpy.CalculateField_management(UnionLayer, 'FID_{0}'.format(update_fc_name), '!FID_{0}! * -1'.format(input_fc_name), "PYTHON_9.3")

    #Clear Selection
    arcpy.SelectLayerByAttribute_management(UnionLayer,"CLEAR_SELECTION")

    # Dissolve the union feature class by update layer fid,
    # and summarize the update fields by their first record
    stat_fields = [[f, 'FIRST'] for f in update_fields]
    output_dissolved_features = arcpy.Dissolve_management(in_features=UnionFeatures, out_feature_class=output_feature_class,
                             dissolve_field='FID_{0}'.format(update_fc_name),
                             statistics_fields=stat_fields,
                             multi_part='MULTI_PART',
                             unsplit_lines='DISSOLVE_LINES')

    arcpy.Delete_management(interim_features)

    # Because of the dissolve step, the output feature class has
    # the update fields listed as 'FIRST_[field]'. Here we
    # add the update field names back into the output feature class,
    # and set them equal to the FIRST_[field]. Then the
    # FIRST_fields are deleted
    for field in update_fields:
        arcpy.AddField_management(output_feature_class, field, 'TEXT')
        arcpy.CalculateField_management(output_feature_class, field, '!FIRST_{0}!'.format(field), "PYTHON_9.3")
        arcpy.DeleteField_management(output_feature_class, 'FIRST_{0}'.format(field))

    arcpy.DeleteField_management(output_feature_class, 'FID_{0}'.format(update_fc_name))
    return output_dissolved_features

########## EXECUTE ######################################################
for row in in_YoI: #JBP
    qry_year = row #JBP
    disposition_lookup = lookup_input
    
    # Create Output Directory if doesn't exist
    if not os.path.exists(out_workspace):
        os.makedirs(out_workspace)
    
    # Create new geodatabase
    out_name = str(qry_year) + ".gdb"
    out_gdb = os.path.join(out_workspace, out_name)
    
    arcpy.CreateFileGDB_management(out_workspace, out_name)
    
    # Set valid feature variables
    brmpIsValid = False
    naip2011IsValid = False
    aac1943IsValid = False
    aac1943IsFallow = False
    cvpIsValid = False
    # Waste sites should always be calculated
    ehsitIsValid = True
    facilitiesIsValid = False
    
    # Check for valid years for data
    qry_yearNum = int(qry_year)
    if qry_yearNum >= 1880:
        brmpIsValid = True
    
    if qry_yearNum >= 1880 and qry_yearNum <= 1943:
        aac1943IsValid = True
    
    if qry_yearNum > 1943: # and  qry_yearNum <= 2050: #GLT - STOMP runs past 2050
        naip2011IsValid = True
        aac1943IsFallow = True

    if qry_yearNum > 1943:
    #     ehsitIsValid = True
        facilitiesIsValid = True
    
    if  qry_yearNum >= 1998:
        cvpIsValid = True
    
    modelYear =  qry_yearNum
    yearString =  str(qry_yearNum)
    validClasses = []
    coverDict = {}
    surfCondDict = {}
    
    # Calculate surface condition from disposition via cover type
    setLookupDicts(disposition_lookup)
    print( str(datetime.now() - start) +"- Disposition Lookup Table Created") #JBP
    # logfile.write(str(datetime.now() - start) +"- Disposition Lookup Table Created" + '\n')
    
    # Build Features
    if brmpIsValid:
        brmp_temp = Build_BRMP(out_gdb, brmp_input, RechargeLookup)
        validClasses.append(brmp_temp)
        print( str(datetime.now() - start) + "- BRMP Vegetation Created"  ) #JBP
        # logfile.write(str(datetime.now() - start) + "- BRMP Vegetation Created"  + '\n')
    
    if aac1943IsValid:
        aac_1943_temp = Build_AAC1943(out_gdb, aac_1943_input)
        validClasses.append(aac_1943_temp)
        print( str(datetime.now() - start) + "- AAC 1943 Created") #JBP
        # logfile.write(str(datetime.now() - start) + "- AAC 1943 Created" + '\n')
    
    if aac1943IsFallow:
        aac_1943_temp = Build_Post_AAC1943(out_gdb, aac_1943_input)
        validClasses.append(aac_1943_temp)
        print(str(datetime.now() - start) + "- AAC 1943 Fallow Created" ) #JBP
        # logfile.write(str(datetime.now() - start) + "- AAC 1943 Fallow Created"  + '\n')
    
    if naip2011IsValid:
        naip_2011_temp = Build_NAIP2011(out_gdb, naip_2011_input)
        validClasses.append(naip_2011_temp)
        print(str(datetime.now() - start)  + "- NAIP 2011 Created") #JBP
        # logfile.write(str(datetime.now() - start)  + "- NAIP 2011 Created" + '\n')
    
    if cvpIsValid:
        cvp_temp = Build_CVP(out_gdb, cvp_input, qry_year)
        validClasses.append(cvp_temp)
        print(str(datetime.now() - start) + "- Cleanup Verification Packages Created")
        # logfile.write(str(datetime.now() - start) + "- Cleanup Verification Packages Created" + '\n')
    
    if ehsitIsValid:
        ehsit_temp = Build_Ehsites(out_gdb, ehsit_input, disposition_input, disposition_lookup, brmpIsValid, brmp_temp)
        validClasses.append(ehsit_temp)
        print(str(datetime.now() - start) + "- Environmental Hazardous Waste Sites Created") #JBP
        # logfile.write(str(datetime.now() - start) + "- Environmental Hazardous Waste Sites Created"+ '\n')
    
    if facilitiesIsValid:
        bggenexs_temp = Build_Bggenexs(out_gdb, bggenexs_input, disposition_input )
        validClasses.append(bggenexs_temp)
        print(str(datetime.now() - start) + "- Facilities Created") #JBP
        # logfile.write(str(datetime.now() - start) + "- Facilities Created" + '\n')
    
        bggensit_temp = Build_Bggensit(out_gdb, bggensit_input, disposition_input)
        validClasses.append(bggensit_temp)
        print(str(datetime.now() - start) + "- Sites Created")
        # logfile.write(str(datetime.now() - start) + "- Sites Created"+ '\n')
    
    valid_count = len(validClasses)
    temp_features = os.path.join(out_gdb, r'UpdatedFeatures_')
    if valid_count > 1:
        base_feature = validClasses[0]
        for x in range(1, valid_count):
            update_feature = validClasses[x]
            temp_name = temp_features + str(x)
            # Requres use of Arc Pro license
            #UpdatedFeatures = arcpy.Update_analysis(base_feature, update_feature,temp_name) #JBP
            UpdatedFeatures = Bootleg_Update(base_feature, update_feature, temp_name, ['Source', 'CoverType', 'SurfCond'])
            base_feature = temp_name
    
    # logfile.write(str(datetime.now() - start) + "- Update Features Created"+ '\n')
    updatedFeaturesFinalString = os.path.join(out_gdb, r'UpdatedFeatures_' + yearString)
    FinalUpdatedFeatures = arcpy.CopyFeatures_management(UpdatedFeatures, updatedFeaturesFinalString)
    
    if valid_count > 1:
        for x in range(1, valid_count):
            temp_name = temp_features + str(x)
            arcpy.Delete_management(temp_name)
    
    # Export Recharge Data
    recharge = Build_RechargeFeatures(out_gdb, FinalUpdatedFeatures, SoilFeatures, RechargeLookup)
    #DeleteExcessRechargeFeatures(recharge) #JBP
    
    # logfile.write(str(datetime.now() - start) + "- Done"+ '\n')
    # logfile.close()
    print(str(datetime.now() - start) + "-  Done") #JBP
    arcpy.AddMessage("Done!")
