///home/itoperations/.jenkins/jobs/overnight-pipeline/config.xml
//https://stackoverflow.com/questions/67141045/how-can-i-call-function-from-another-file-in-jenkins-pipeline

import groovy.json.JsonSlurper
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

def executeTestFiles(fileDetails, containerQuantity, env, addInfo, CONFIG_FILE_NAME){
    fileDetails.each{ key, value ->

        allFound = false
        
        paths = []
        selections = value.replaceAll(/[\{\} ]/,"").split(",")
        
        selections.each{paths.add("")}
        

            selections.each{
                if(!it.contains("all")){
                    if(it.contains("selection_")){
                        index = it.split('selection_')[1].split('=')[0]
                        paths[index.toInteger()] = it.split("selection_${index}=")[1]
                    }
                } else {
                    allFound = true
                }
            }


        selectedFile = env.DATA_HOME
        paths.each{
            if(it != ""){
                selectedFile+="/${it}"
            }
        }
        selectedFile += "/"
        selections=[]

        if(allFound){
            sh(returnStdout: true, script: """
                find ${selectedFile} -regex ".*${CONFIG_FILE_NAME}"
            """).split("\n").each{
                selections.add(it - ("/" + CONFIG_FILE_NAME))
            }
        } else {
            selections.add(selectedFile)
        }

        selections.eachWithIndex{item, index ->
            print("selection[${index}] = ${item}")
        }

        selections.eachWithIndex{item, index ->
            
            indexedName = "${key}_${index.toString()}"
            
            is_performance = testIsPerformance(item)
            executeTest(item, containerQuantity, "${key}_${index.toString()}", is_performance, addInfo)
            queryTest(containerQuantity, is_performance)
            tearDown(is_performance, env.PV_BOX, containerQuantity, env.PV_DEPLOY_PATH)
            
            sh(returnStdout:true, script:"""
                
                for x in \$(ls .); do \
                    \$( rm -rf \$x );
                done
                    
                curl -X POST \
                    -d '{"TestName": "${key}_${index.toString()}"}' \
                    -H 'Content-Type: application/json' \
                    -o "./${key}_${index.toString()}.zip" \
                    "${env.TH_BOX}/getTestOutputFolder"
                    
                unzip -o ./${key}_${index.toString()}.zip \
                -d ./${key}_${index.toString()}
                
            """)
            
            publishHTML (target : [allowMissing: false,
                alwaysLinkToLastBuild: true,    
                keepAll: true,
                reportDir: "${env.OUTPUTS}/${key}_${index.toString()}",
                reportFiles: '*.html',
                reportName: "Report_${key}_${index.toString()}"
                ])
        }
    }
}

def getPrefixes(fileNames, addInfoLabel){
    prefixes = fileNames.collect()
    prefixes.collect{it += "={"}
    prefixes.add(addInfoLabel)

    return prefixes
}

def getFileDetails(int filesToSelect, String containerQuantity, String FILE_SELECT, List fileNames) {

    multiSelectReturnTruncated = env.FILE_SELECT[1..env.FILE_SELECT.size()-2]
    fileNameString = multiSelectReturnTruncated

    addInfoLabel = "Additional Information="

    prefixes = getPrefixes(fileNames, addInfoLabel)
    fileNames.eachWithIndex{value, key -> print("filenames[${key}] = ${value}")}

    fileDetails = [:]
    fileNames.each{
        fileDetails[it] = extractFromStringUsingPrefixes(env.FILE_SELECT, it + "={", prefixes).replaceAll(" ","")
    }
    addInfo = extractFromStringUsingPrefixes(env.FILE_SELECT, addInfoLabel, prefixes).trim()
    if(addInfo != ""){
        try{
            def slurped = new JsonSlurper().parseText(addInfo)
        } catch (Exception e){
            error("Invalid 'additional info' JSON provided. Please try again.")
        }
    }
    return fileDetails
}

def createTestSelectionArguments(List TEST_PATHS, List ITEM_LIST){
    VARIABLE_DESCRIPTIONS = []
    for(int i = 0; i < TEST_PATHS.max{it.size()}.size()-1;i++){
        VARIABLE_DESCRIPTIONS.add(
            [
                label:"folder level ${i+1}",
                variableName:"selection_${i}"
            ]
        )
    }
    
    multiArgs = [
        name:"Test selection",
        description:"Please select the test to run.",
        decisionTree:[
            variableDescriptions:VARIABLE_DESCRIPTIONS,
            itemList:ITEM_LIST
        ]
    ]
    return multiArgs
}

def parseTestPaths(List TEST_PATHS_RAW, String testFileName = "test_config.yaml"){
    TEST_PATHS_RAW.eachWithIndex{path,index -> 
        TEST_PATHS_RAW[index] = path.split("/") as List
    }
    
    TEST_PATHS = []
    TEST_PATHS_RAW.eachWithIndex{path, outerIndex ->
        path.eachWithIndex{ item, innerIndex ->
            if(item == testFileName){
                TEST_PATHS.add(TEST_PATHS_RAW[outerIndex][1..innerIndex])
            }
        }
    }
    return TEST_PATHS
}

def extractFromStringUsingPrefixes(String overall, String targetPrefix, prefixes){

    if(!overall.contains(targetPrefix)){return ""}

    startIndex       = overall.indexOf(targetPrefix)
    endIndex         = startIndex + targetPrefix.size()
    smallestDistance = 999999

    prefixes.each{
        if(it != targetPrefix){
            if(overall.contains(it)){
                matchIndex = overall.indexOf(it)
                if(matchIndex > endIndex){
                    distance = matchIndex - endIndex
                    if(smallestDistance > distance){
                        smallestDistance = distance
                    }
                }
            }
        }
    }

    if(smallestDistance == 999999){
        return removeLastCharsIf(overall[endIndex..overall.size() - 1], ",}")
    }

    if(smallestDistance < 2){
        return ""
    }

    return removeLastCharsIf(overall[endIndex..endIndex + smallestDistance - 2], ",")
}

def removeLastCharsIf(String input, String lastChars){

    output = input
    lastChars.each{

        if(output.size() > 0 && lastChars.contains(output[output.size()-1]) ){
            if(output.size() == 1){
                output = ""
            } else {
                output = output[0..output.size()-2]
            }
        } else {
            output = output
        }
    }

    return output
}

def putInNestedMap(Map Input, List<String> Location, int Depth, int MaxDepth ){

    if(Depth > MaxDepth){
        echo "Max depth reached, aborting"
        return Input
    }
    
    currentLoc = Location[0]
    Input.put("all","all")
    
    if(!Location.getClass().toString().contains('ArrayList') || Location.size() < 2){
        Input.put(currentLoc, currentLoc)
        return Input
    }
    
    if(!Input.keySet().contains(currentLoc)){
        Input.put(currentLoc,[:])
    }

    Input.put(currentLoc, putInNestedMap(Input[currentLoc], Location[1..-1], Depth +1, MaxDepth))
    
    return Input
    
}

def convertToDecisionTree(Map Input, List returnBuilder,int Depth, int MaxDepth){

    if(Depth > MaxDepth){
        echo "Max depth reached, aborting"
        return returnBuilder
    }
    
    Input.each{ key,value ->
        if(key == value){
            returnBuilder.add([
                "label": key, 
                "value":value
            ])
        } else {
            returnBuilder.add([
                "label": key, 
                "value": key,
                "children":convertToDecisionTree(value, [], Depth+1, MaxDepth)
            ])
        }
    }
    
    return returnBuilder
}

def testIsPerformance(String selectedTest){

    test_yaml=sh(
        returnStdout: true,
        script: """
            cd ${selectedTest}
            cat test_config.yaml
        """
    )
    
    return (test_yaml.contains("type") && test_yaml.contains("Performance"))
}

def executeTest(String selectedTest, String containerQuantity, String fileName, Boolean is_performance, String addInfo){

    if(is_performance){
        sh(script:"""
            ssh root@${env.PV_BOX} "cd ${env.PV_DEPLOY_PATH} &&
            export PV_COMPOSE_FILE='docker-compose-1AER_${containerQuantity}AEO.yml' && 
            ./run_performance_test.sh" 21>/dev/null || true
        """)
    } else {
        sh(script:"""
            ssh root@${env.PV_BOX} "cd ${env.PV_DEPLOY_PATH} &&
            ${env.PV_DEPLOY_PATH}/run_functional_test.sh"
        """)
    }
    
    selectedSplit = selectedTest.split("/")
    zipName = selectedSplit[selectedSplit.size()-1]
    
    url = "\"http://${env.TH_BOX}/upload/named-zip-files\""
    form = "\"${fileName}=@./${fileName}.zip\""
    data = """'{"TestName":"${fileName}\""""
    header = "\"Content-Type: application/json\""

    if(addInfo != ""){
        data += ", ${addInfo}}'"
    } else {
        data += "}'"
    }

    curl_test_cases_return=sh(
        returnStdout: true,
        
        script:"""
            cd ${selectedTest}/..;
            
            zip -r "${fileName}.zip" ${zipName} &&
            curl --location --request POST ${url} --form ${form} &&
            curl -X POST -d ${data} -H ${header} "http://${env.TH_BOX}/startTest" &&
            rm "./${fileName}.zip"
        """
    )
}

def queryTest(String containerQuantity, Boolean is_performance){

    waitInterval = env.WAIT_INTERVAL.toInteger()
    notComplete = true

    while(notComplete){
        sleep(time:waitInterval, unit:"SECONDS")
        isTestRunning = sh(
            returnStdout:true,
            script:"""
                curl http://${env.TH_BOX}/isTestRunning
            """
        )
        
        echo "Progress: ${isTestRunning}"
        
        if(isTestRunning.contains("false")){
            notComplete = false
        }
    }
}

def tearDown(boolean is_performance, String PV_BOX, String containerQuantity, String PV_DEPLOY_PATH){

    if(is_performance){
        sh(
            returnStdout: true,
            script:"""
                ssh root@${PV_BOX} "cd ${PV_DEPLOY_PATH} &&
                export PV_COMPOSE_FILE='docker-compose-1AER_${containerQuantity}AEO.yml' &&
                ./tear_down_pv.sh || true"
            """
        )
    } else {
        sh(
            returnStdout: true,
            script:"""
                ssh root@${PV_BOX} "cd ${PV_DEPLOY_PATH} &&
                ./tear_down_pv.sh || true"
            """
        )
    }
}

return this