    pipeline {
        agent any
        stages {
            // this requires the 'multiselect-parameter', 'file parameter' and 'htmlpublisher'  plugins
            stage("TH-main-runtime"){
                steps {
                    script {
                        env.DATA_HOME         = "$JENKINS_HOME/../data-scripts/jenkins_test_cases"
                        env.OUTPUTS           = "$JENKINS_HOME/workspace/test-harness-pipeline-test"
                        env.PV_BOX            = "172.16.0.15"
                        env.TH_BOX            = "172.16.0.15:8800"
                        env.PV_DEPLOY_PATH    = "/home/itoperations/munin/deploy"
                        env.CONFIG_FILE_NAME  = "test_config.yaml"
                        
                        TEST_CATEGORIES=[:]
                        TEST_PATHS_RAW=sh(
                            returnStdout: true,
                        
                            script:"""
                                cd $DATA_HOME
                                find . -type f
                            """
                        ).split("\n") as List
                        
                        withFileParameter('customTestFile'){
                            
                            customTestContent=sh(returnStdout:true, script:"""
                                cat $customTestFile 2>/dev/null
                            """)
                            
                            if(customTestContent.size() < 1){
                                
                                TEST_PATHS_RAW.eachWithIndex{path,index -> 
                                    TEST_PATHS_RAW[index] = path.split("/") as List
                                }
                                
                                TEST_PATHS = []
                                TEST_PATHS_RAW.eachWithIndex{path, outerIndex ->
                                    path.eachWithIndex{ item, innerIndex ->
                                        if(item == "test_config.yaml"){
                                            TEST_PATHS.add(TEST_PATHS_RAW[outerIndex][1..innerIndex])
                                        }
                                    }
                                }
                                
                                results = [:]
                                TEST_PATHS.each{
                                    results = putInNestedMap(results, it, 0, 10)
                                }
                                
                                
                                ITEM_LIST = []
                                ITEM_LIST = convertToDecisionTree(results,ITEM_LIST,0,10)
                                
                                VARIABLE_DESCRIPTIONS = []
                                for(int i = 0; i < TEST_PATHS.max{it.size()}.size()-1;i++){
                                    VARIABLE_DESCRIPTIONS.add(
                                        [
                                            label:"folder level ${i+1}",
                                            variableName:"selection_${i}"
                                        ]
                                    )
                                }
                                
                                fileSelectionName = "Number of files selected"
                                numberOfFilesSelected = validatingString(
                                    name:fileSelectionName,
                                    defaultValue:"1",
                                    regex:/[0-9]+/,
                                    description:"""\
            How many files or folders do you want to select? Selecting all files in a folder counts as one item.\
            Multiple tests under one name (selecting all) shall be run in series, and identified using the form [TESTNAME]_[INDEX] e.g. TCASE_001_0"""
                                )
                                
                                testCaseName = "Test case names"
                                testCaseNames = validatingString(
                                    name:testCaseName,
                                    defaultValue:"TCASE_001",
                                    regex:/[a-zA-Z0-9, _-]*/,
                                    description:"Please enter the names of the test cases you will be using as a comma-delineated list."
                                )
                                
                                containerQuantities = multiselect([
                                        name:"Container quantity selection",
                                        description:"Please select how many containers are required",
                                        decisionTree:[
                                            variableDescriptions:[[
                                                "label":"Quantity of containers",
                                                "variableName":"containerQuantity"
                                            ]],
                                            itemList:[
                                                ["value":"1"],
                                                ["value":"4"],
                                                ["value":"8"],
                                            ]
                                        ]
                                ])
                                
                                env.SELECTION_QUANTITIES = input(
                                    message:"Please enter the desired information.",
                                    ok:"Continue",
                                    parameters:[numberOfFilesSelected,testCaseNames,containerQuantities]
                                )
                                
                                selections = []
                                selectionQuantites = env.SELECTION_QUANTITIES.split('=').collect{it.replaceAll(/[\{\} ]/,"")}
                                
                                multiArgs = [
                                        name:"Test selection",
                                        description:"Please select the test to run.",
                                        decisionTree:[
                                            variableDescriptions:VARIABLE_DESCRIPTIONS,
                                            itemList:ITEM_LIST
                                        ]
                                ]
                                
                                selectionReplaced = env.SELECTION_QUANTITIES.replaceAll(/[\{\}]/,"")
                                filesToSelect = selectionReplaced.split(/${fileSelectionName}=/)[1].split(",")[0].toInteger()
                                testCaseNames = selectionReplaced.split(/${testCaseName}=/)[1]
                                containerQuantity = env.SELECTION_QUANTITIES.split("containerQuantity=")[1].split("}")[0]
                                
                                if(testCaseNames.contains(fileSelectionName)){
                                    
                                    selectionSplit = testCaseNames.split(/,${fileSelectionName}/)[0]
                                    testCaseNames = selectionSplit
                                } else {
                                    
                                    testCaseNames = testCaseNames.split(",")
                                }
                                
                                fileNames=[]
                                for(int i = 0; i < filesToSelect; i++){
                                    if(i <= filesToSelect && 
                                        testCaseNames[i] != null &&
                                        testCaseNames[i].size() > 0){
                                        multiArgs.name = testCaseNames[i]
                                    } else {
                                        multiArgs.name = "TCASE_${UUID.randomUUID().toString()}"
                                    }
                                    fileNames.add(multiArgs.name)
                                    selections.add(multiselect(multiArgs))
                                }
                                
                                env.FILE_SELECT = input(
                                    message:"Please select the desired files/folders",
                                    ok:"Submit",
                                    parameters:selections
                                )
                                
                                multiSelectReturnTruncated = env.FILE_SELECT[1..env.FILE_SELECT.size()-2]
                                
                                fileDetails = [:]
                                fileNames.eachWithIndex{item, index ->
                                    if(multiSelectReturnTruncated.contains("${item}")){
                                        
                                        itemMatch = multiSelectReturnTruncated.split("${item}=")
                                        
                                        matchSize = 0
                                        itemMatched = itemMatch[1]
                                        fileNames.each{
                                            temp = itemMatched.split(it)[0]
                                            if(itemMatched.size() - temp.size() > matchSize){
                                                
                                                itemMatched = temp
                                                matchSize = itemMatched.size()
                                            }
                                        }
                                        
                                    fileDetails.put(item, itemMatched)
                                    
                                    } else {
                                        fileDetails.put(item, multiSelectReturnTruncated)
                                    }
                                    
                                }
                                
                                fileDetails.each{ key, value ->
                                    allFound = false
                                    
                                    paths = []
                                    selections = value.replaceAll(/[\{\} ]/,"").split(",")
                                    
                                    selections.each{paths.add("")}
                                    
                                    selections.each{
                                        if(!it.contains("all")){
                                            index = it.split('selection_')[1].split('=')[0]
                                            paths[index.toInteger()] = it.split("selection_${index}=")[1]
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
                                        // will have to loop through them here
                                        sh(returnStdout: true, script: """
                                            find ${selectedFile} -regex ".*${CONFIG_FILE_NAME}"
                                        """).split("\n").each{
                                            selections.add(it - ("/" + CONFIG_FILE_NAME))
                                        }
                                    } else {
                                        selections.add(selectedFile)
                                    }
                                    
                                    echo "selections.each starting"
                                    selections.eachWithIndex{item, index ->
                                        
                                        indexedName = "${key}_${index.toString()}"
                                        
                                        is_performance = testIsPerformance(item)
                                        executeTest(item, containerQuantity, "${key}_${index.toString()}", is_performance, false)
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
                                            ])// reportTitles: 'The Report'])
                                    }
                                }
                                
                            } else {
                                
                                sh(script:"""mv ${customTestFile} ./customTest.zip""")
                                
                                testCaseName=validatingString(
                                    name:"Test Case Name",
                                    defaultValue:"TCASE_001",
                                    regex:/[a-zA-Z0-9, _-]*/,
                                    description:"Please enter the name of the test case you have uploaded."
                                )
                                
                                containerQuantities = multiselect([
                                    name:"Container quantity selection",
                                    description:"Please select how many containers are required",
                                    decisionTree:[
                                        variableDescriptions:[[
                                            "label":"Quantity of containers",
                                            "variableName":"containerQuantity"
                                        ]],
                                        itemList:[
                                            ["value":"1"],
                                            ["value":"4"],
                                            ["value":"8"],
                                        ]
                                    ]
                                ])
                                
                                env.TEST_DATA = input(
                                    message:"Please enter the desired information.",
                                    ok:"Continue",
                                    parameters:[testCaseName,containerQuantities]
                                )
                                
                                testDataSplit = env.TEST_DATA.replaceAll(/[\{\}]/,"").split(",")
                                containerQuantity="1"
                                fileName="."
                                testDataSplit.each{
                                    if(it.contains("containerQuantity")){
                                        containerQuantity = (it - "Container quantity selection=containerQuantity=").replaceAll(" ","")
                                    } else {
                                        fileName = it - "Test Case Name=".trim()
                                    }
                                }
                                
                                sh(returnStdout:true,script:"""
                                    rm -rf ./${fileName} 21>/dev/null ;
                                    unzip -o customTest.zip \
                                    -d ./${fileName} 21>/dev/null
                                """)
                                configFileLoc=sh(returnStdout:true,
                                    script:"""
                                        find "./${fileName}" -regex ".*${CONFIG_FILE_NAME}" 
                                    """
                                )
                                configFilePath=configFileLoc.split("/")
                                selectedTestFolder=configFilePath[0..configFilePath.size()-2].join("/")
                                
                                is_performance = testIsPerformance(selectedTestFolder)
                                executeTest(selectedTestFolder, containerQuantity, fileName, is_performance, false)
                                queryTest(containerQuantity, is_performance)
                                tearDown(is_performance, env.PV_BOX, containerQuantity, env.PV_DEPLOY_PATH)
                                
                                sh(returnStdout:true, script:"""
                                    
                                    for x in \$(ls .); do \
                                        \$( rm -rf \$x );
                                    done
                                        
                                    curl -X POST \
                                        -d '{"TestName": "${fileName}"}' \
                                        -H 'Content-Type: application/json' \
                                        -o "./${fileName}.zip" \
                                        "${env.TH_BOX}/getTestOutputFolder"
                                        
                                    unzip -o ./${fileName}.zip \
                                    -d ./${fileName}
                                    
                                """)
                                
                                publishHTML (target : [allowMissing: false,
                                    alwaysLinkToLastBuild: true,
                                    keepAll: true,
                                    reportDir: "${fileName}",
                                    reportFiles: '*.html',
                                    reportName: "Report_${fileName}"
                                    ])// reportTitles: 'The Report'])
                            }
                        }
                    }
                }
            }
        }
        
        post { always {
            archiveArtifacts artifacts: "**.zip", fingerprint: true
            tearDown(false,env.PV_BOX,"8", env.PV_DEPLOY_PATH)
        }}
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

    def executeTest(String selectedTest, String containerQuantity, String fileName, Boolean is_performance, Boolean is_upload){
        
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
        
        if(!is_upload){
            
            selectedSplit = selectedTest.split("/")
            zipName = selectedSplit[selectedSplit.size()-1]
            
            curl_test_cases_return=sh(
                returnStdout: true,
                
                script:"""
                    cd ${selectedTest}/..;
                    
                    zip -r "${fileName}.zip" ${zipName} &&
                    curl --location --request POST "http://${env.TH_BOX}/upload/named-zip-files" --form "${fileName}=@./${fileName}.zip" &&
                    curl -X POST -d '{"TestName":"${fileName}"}' -H "Content-Type: application/json" "http://${env.TH_BOX}/startTest" &&
                    rm "./${fileName}.zip"
                """
            ).split("\n") as List
        } else {
            sh(
                returnStdout:true,
                script:"""
                    curl -X POST -d '{"TestName":"${fileName}"}' -H "Content-Type: application/json" "http://${env.TH_BOX}/startTest
            """
            )
            
        }
        
    }

    def queryTest(String containerQuantity, Boolean is_performance){
            
        waitTotal = env.WAIT_TIME_SECONDS.toInteger()
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