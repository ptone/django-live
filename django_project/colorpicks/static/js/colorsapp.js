console.log("app loading");


var ColorChoice = Backbone.Model.extend({
    defaults: function() {
        return{
            color_choice: "000000",
            name: "unnamed user",
            identifier: "",
            email: ""
        };
    },

    toJSON: function() {
        var data = _.clone(this.attributes); 
        delete data.id;
        console.log(data);
        return data
    },

    save: $.throttle(500, function(){
        console.log("saving");
        Backbone.Model.prototype.save.call(this);
    }),

});

var ColorChoiceArray = Backbone.Collection.extend({
    model: ColorChoice,
    url: "/api/colors/"
});

var ColorChoiceView = Backbone.View.extend({
    tagName: "li",

    initialize: function (){},

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
        // array.on('reset', this.addAll, this);
        // array.on('all', this.render, this);
        console.log("Fetching choices");
        this.collection.on("reset", function() { this.addAll() }, this);
        this.collection.fetch();

        // this.collection.fetch({
            // success: this.addPostFetch,});
        // this.addAll();
    },

    addOne: function(choiceItem) {
        console.log('adding one');
        console.log(choiceItem);
        console.log(choiceItem.get("color_choice"));
        console.log(this.mycolorid);

        // console.log(choiceItem.url());
        if (choiceItem.id != this.mycolorid){
        var view = new ColorChoiceView({model:choiceItem});
        this.$el.append(view.render().el);
        } else {
            console.log("my color");
            var view = new MyColorChoiceView({model:choiceItem});
            $("#mycolor").html(view.render().el);

            // $("#mycolor-display").css("background-color", choiceItem.get("color_choice"));
            $("#id_color_choice").val(choiceItem.get("color_choice"));
            console.log($("#id_color_choice").val());

            $(".colorpicker").miniColors({
                change: function(hex, rgb){
                    choiceItem.set("color_choice", hex);
                    choiceItem.save();
                    // $("#mycolor-display").css("background-color", hex);
                    }
                    });
            console.log("color widget applied?");
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
