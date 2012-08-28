
// usage: log('inside coolFunc', this, arguments);
// paulirish.com/2009/log-a-lightweight-wrapper-for-consolelog/
window.log = function(){
  log.history = log.history || [];   // store logs to an array for reference
  log.history.push(arguments);
  if(this.console) {
    arguments.callee = arguments.callee.caller;
    var newarr = [].slice.call(arguments);
    (typeof console.log === 'object' ? log.apply.call(console.log, console, newarr) : console.log.apply(console, newarr));
  }
};

window.socket = io.connect('http://localhost:8008');
log(window.socket);

socket.emit("testemit", {test:"data"});
socket.emit("identify", {'identifier':$.cookie("sessionid")});

console.log("app loading");


var ColorChoice = Backbone.Model.extend({
    urlRoot: 'color',
    noIoBind: false,
    socket: window.socket,

    initialize: function () {
       _.bindAll(this, 'serverChange', 'serverDelete', 'modelCleanup');

        /*!  if we are creating a new model to push to the server we don't want to
        * iobind as we only bind new models from the server. This is because the
        * server assigns the id.
        */
        if (!this.noIoBind) {
            this.ioBind('update', this.serverChange, this);
            this.ioBind('delete', this.serverDelete, this); }
    },

    defaults: function() {
        return{
            color_choice: "#000000",
            name: "unnamed user",
            identifier: "",
            email: ""
        };
    },

    // this is being removed because of DRF not wanting the ID back
    // toJSON: function() {
        // var data = _.clone(this.attributes);
        // delete data.id;
        // return data
    // },

    // save: $.throttle(500, function(){
        // Backbone.Model.prototype.save.call(this);
    // }),

    serverChange: function (data) {
    // Useful to prevent loops when dealing with client-side updates (ie: forms).
    console.log('getting server change');
    console.log(this.get('name'));
    console.log(data);
    data.fromServer = true;
    this.set(data);
    // saving at this point would cause a loop
    this.change();
  },

  serverDelete: function (data) {
    console.log("serverDelete");
    if (this.collection) {
    console.log('has collection');
      this.collection.remove(this);
    } else {
    console.log('has NO collection');
      this.trigger('remove', this);
    }
    this.modelCleanup();
  },
  modelCleanup: function () {
    this.ioUnbindAll();
    return this;
  }


});

var ColorChoiceArray = Backbone.Collection.extend({
    model: ColorChoice,
    socket:window.socket,

    url: "colors",

    initialize: function () {
    console.log("initialize collection")
    _.bindAll(this, 'serverCreate', 'collectionCleanup');
    this.ioBind('create', this.serverCreate, this);
    
    },

  serverCreate: function (data) {
    // make sure no duplicates, just in case
    console.log('serverCreate');
    console.log(data);
    var exists = this.get(data.id);
    if (!exists) {
      this.add(data);
    } else {
      data.fromServer = true;
      exists.set(data);
    }
  },

  collectionCleanup: function (callback) {
    this.ioUnbindAll();
    this.each(function (model) {
      model.modelCleanup();
    });
    return this;
  }
});

var ColorChoiceView = Backbone.View.extend({
    tagName: "li",

    initialize: function(){
        _.bindAll(this, "render");
        this.model.bind('change', this.render);
    },

    template: _.template($('#item-template').html()),

    events: {},

    render: function () {
        this.$el.html(this.template(this.model.toJSON()));
        return this;},

});

var MyColorChoiceView = Backbone.View.extend({
    // the view to handle current users color choice
    tagName: "div",

    initialize: function(){
        _.bindAll(this, "render");
        this.model.bind('change', this.render);
    },

    template: _.template($('#mychoice-template').html()),

    render: function () {
        console.log("rendering mycolor");
        this.$el.html(this.template(this.model.toJSON()));
        // jquery add minicolors
        // this is not working from inside render
        //
        // $(".colorpicker").miniColors({
            // change: $.throttle(250, function(hex, rgb){
                // $("#mycolor-display").css("background-color", hex)})
                // });
        $("#mycolor-display").on("click", (function(){
            $("#id_color_choice").triggerHandler("focus");
            }));

        // $("#mycolor-display").click(function(){
            // $("#id_color_choice").triggerHandler("focus");
            // });

        return this;},

});

var ArrayView = Backbone.View.extend({

    mycolorid: parseInt($.cookie('colorid')),

    initialize: function() {
        this.collection.on('add', this.addOne, this);
        this.collection.on('remove', this.removeOne, this);
        // array.on('all', this.render, this);
        this.collection.on("reset", function() { this.addAll() }, this);
        console.log("Fetching choices");
        this.collection.fetch();

        // this.collection.fetch({
            // success: this.addPostFetch,});
        // this.addAll();
    },

    addOne: function(choiceItem) {

        console.log(choiceItem.url());
        socket.emit("subscribe", {url:choiceItem.url()});

        if (choiceItem.id != this.mycolorid){
        var view = new ColorChoiceView({model:choiceItem});
        this.$el.append(view.render().el);
        } else {
            console.log("my color");
            var view = new MyColorChoiceView({model:choiceItem});
            $("#mycolor").html(view.render().el);

            // $("#mycolor-display").css("background-color", choiceItem.get("color_choice"));
            $("#id_color_choice").val(choiceItem.get("color_choice"));
            // console.log($("#id_color_choice").val());

            $(".colorpicker").miniColors({
                change: function(hex, rgb){
                    choiceItem.set("color_choice", hex);
                    choiceItem.save();
                    // $("#mycolor-display").css("background-color", hex);
                    }
                    });

            $("#mycolor-display").on("click", (function(){
                $("#id_color_choice").triggerHandler("focus");
                }));

        }
    },

    addPostFetch: function(collection, response) {
        console.log(this); // == Window /colors/app/
        this.addAll();
    },

    addAll: function() {
        console.log(this); // == Window /colors/app/
        console.log("in addAll")
        console.log(this.collection.length)
        this.collection.each(this.addOne.bind(this));
    },

    removeOne: function(colorchoice) {
        console.log("remove one");
        this.$("#color-" + colorchoice.id).parent().remove();
    }

});


$(function(){
    console.log("app init started");
    var colorlist = new ColorChoiceArray();

    new ArrayView({
        el:$("#color-choices-list"),
        collection: colorlist,
    });

    console.log("app init done");
    });
