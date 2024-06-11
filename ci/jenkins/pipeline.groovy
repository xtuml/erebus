import groovy.json.JsonSlurper

pipeline {
    agent any
    stages {
        // this requires the 'multiselect-parameter', 'file parameter' and 'htmlpublisher'  plugins
        stage("TH-main-runtime"){
            steps {
                script {
                    env.DATA_HOME         = "$JENKINS_HOME/../data-scripts/jenkins_test_cases"
                    env.OUTPUTS           = "$JENKINS_HOME/workspace/test-harness-pipeline-test"
                    env.PV_BOX            = "172.16.0.21"
                    env.TH_BOX            = "172.16.0.16:8800"
                    env.PV_DEPLOY_PATH    = "/home/itoperations/munin_1.3.1-midstage2/deploy"
                    env.WAIT_INTERVAL     = "10"
                    env.CONFIG_FILE_NAME  = "test_config.yaml"

                    // getting around scoping issuesx
                    addInfo = ""
                    extraInfo = validatingString(
                        name:"Additional Information",
                        defaultValue:"",
                        regex:/[\w\W]*/,
                        description:"""Please add any additional flags that need to be provided to the /startTest invocation."""
                    )
                    
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
                            
                            TEST_PATHS = load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").parseTestPaths(
                                TEST_PATHS_RAW
                            )
                            
                            results = [:]
                            TEST_PATHS.each{
                                results = load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").putInNestedMap(
                                    results,
                                    it, 
                                    0, 
                                    10
                                )
                            }
                            
                            
                            ITEM_LIST = []
                            ITEM_LIST = load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").convertToDecisionTree(
                                results,
                                ITEM_LIST,
                                0,
                                10
                            )
                            
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
                                description:"""How many files or folders do you want to select? Selecting all files in a folder counts as one item. Multiple tests under one name (selecting all) shall be run in series, and identified using the form [TESTNAME]_[INDEX] e.g. TCASE_001_0"""
                            )
                            
                            testCaseName = "Test case names"
                            testCaseNames = validatingString(
                                name:testCaseName,
                                defaultValue:"TCASE_001",
                                regex:/[a-zA-Z0-9, _]*/,
                                description:"Please enter the names of the test cases you will be using as a comma-delineated list. Please note, this text must match the following regex; '[a-zA-Z0-9_]*' and can only contain alphanumeric characters + underscores as a result."
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
                            
                            fileSelectionInput = [
                                    name:"Test selection",
                                    description:"Please select the test to run.",
                                    decisionTree:[
                                        variableDescriptions:VARIABLE_DESCRIPTIONS,
                                        itemList:ITEM_LIST
                                    ]
                            ]

                            prefixes = ["${fileSelectionName}=","${testCaseName}=","Container quantity selection={containerQuantity="]
                            filesToSelect = load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").extractFromStringUsingPrefixes(
                                env.SELECTION_QUANTITIES,
                                prefixes[0],
                                prefixes
                            ).toInteger()
                            testCaseNames = load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").extractFromStringUsingPrefixes(
                                env.SELECTION_QUANTITIES,
                                prefixes[1],
                                prefixes
                            ).replaceAll(" ", "")
                            containerQuantity = load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").extractFromStringUsingPrefixes(
                                env.SELECTION_QUANTITIES,
                                prefixes[2],
                                prefixes
                            ) - "}"
                            
                            if(testCaseNames.contains(fileSelectionName)){
                                
                                selectionSplit = testCaseNames.split(/,${fileSelectionName}/)[0]
                                testCaseNames = selectionSplit
                            } else {
                                
                                testCaseNames = testCaseNames.split(",")
                            }
                            
                            selections = []

                            fileNames=[]
                            for(int i = 0; i < filesToSelect; i++){
                                if(i <= filesToSelect && 
                                    testCaseNames[i] != null &&
                                    testCaseNames[i].size() > 0){
                                    fileSelectionInput.name = testCaseNames[i]
                                } else {
                                    fileSelectionInput.name = "TCASE_${UUID.randomUUID().toString()}"
                                }
                                fileNames.add(fileSelectionInput.name)
                                selections.add(multiselect(fileSelectionInput))
                            }

                            selections.add(extraInfo)
                            
                            env.FILE_SELECT = input(
                                message:"Please select the desired files/folders",
                                ok:"Submit",
                                parameters:selections
                            )

                            fileDetails = load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").getFileDetails(
                                filesToSelect,
                                containerQuantity,
                                FILE_SELECT,
                                fileNames
                            )
                            
                            load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").executeTestFiles(
                                fileDetails,
                                containerQuantity,
                                env,
                                addInfo,
                                CONFIG_FILE_NAME
                            )
                            
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
                                parameters:[testCaseName,containerQuantities,extraInfo]
                            )

                            testDataSplit = env.TEST_DATA.replaceAll(/[\{\}]/,"").split(",")
                            containerQuantity="1"
                            fileName="."

                            prefixes = ["Container quantity selection={containerQuantity=", "Test Case Name=", "Additional Information="]
                            containerQuantity = load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").extractFromStringUsingPrefixes(
                                env.TEST_DATA,
                                prefixes[0],
                                prefixes
                            ).replaceAll(" ","")
                            fileName = load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").extractFromStringUsingPrefixes(
                                env.SELECTION_QUANTITIES,
                                prefixes[1],
                                prefixes
                            ).trim()
                            addInfo = load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").extractFromStringUsingPrefixes(
                                env.SELECTION_QUANTITIES,
                                prefixes[2],
                                prefixes
                            )

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
                            
                            is_performance = load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").testIsPerformance(
                                selectedTestFolder
                            )
                            load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").executeTest(
                                selectedTestFolder, 
                                containerQuantity, 
                                fileName, 
                                is_performance, 
                                addInfo
                            )
                            load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").queryTest(
                                containerQuantity, 
                                is_performance
                            )
                            load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy").tearDown(
                                is_performance, 
                                env.PV_BOX, 
                                containerQuantity, 
                                env.PV_DEPLOY_PATH
                            )
                            
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
                                ])
                        }
                    }
                }
            }
        }
    }
    
    post { always {
        archiveArtifacts artifacts: "**.zip", fingerprint: true
        tearDown(
            false,
            env.PV_BOX,
            "8", 
            env.PV_DEPLOY_PATH
        )
    }}
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