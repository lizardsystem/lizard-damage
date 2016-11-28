node {
   stage "Checkout"
   checkout scm

   stage "Build"
   sh "docker-compose down -v"
   sh "docker-compose build"
   sh "docker-compose run web python bootstrap.py"
   sh "docker-compose run web bin/buildout"

   stage "Test"
   sh "docker-compose run web bin/test"
   sh "docker-compose down -v"

}
