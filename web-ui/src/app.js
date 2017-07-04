// Copyright 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
// Licensed under the Amazon Software License (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at
//     http://aws.amazon.com/asl/
// or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied. See the License for the specific language governing permissions and limitations under the License.

if(!apiBaseUrl || !apiKey){
    alert("API base URL and/or API key are not set.")
}

var axiosInstance = axios.create({
  baseURL: apiBaseUrl, //From apigw.js
  headers: {'X-api-key': apiKey}, //From apigw.js
  timeout: 6000,
});


var app = new Vue({
  el: '#app',
  
  methods: {
  	fetchFrames: function(){
  		axiosInstance.get('enrichedframe')
			.then(response => {
		      // JSON responses are automatically parsed.
		      console.log(response.data);
		      this.enrichedframes = response.data;
		    })
		    .catch(e => {
		      //this.errors.push(e);
		      console.log(e);
		    })
  	},
  	toggleFetchFrames: function(){
  		if(!this.autoload){
  			//this.autoloadTimer.stop();
  			this.autoloadTimer = setInterval(this.fetchFrames, 3000);
  			this.autoload=true;
  		}
  		else{
  			//this.autoloadTimer.start();
  			clearInterval(this.autoloadTimer);
  			this.autoload = false;
  		}

  	}
  },
  created: function () {
    this.toggleFetchFrames();
  },
  data: {
    enrichedframes : [],
    autoload: false,
  	autoloadTimer : null,
  },
})



