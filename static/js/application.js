$(document).ready(function() {
    
    $('.tool').tooltip();
    
    $('.pop').popover();
    $(".fancybox").fancybox({
        'type': 'image',
        helpers : {
            title : {
                type : 'float'
            },
        },
        tpl : {
            error : 'Can not dispaly preview, unsupported format.'
        },
        'autoSize': 'false'
    });
    
    Popup = {
        init : function () {
            $('a.action_print').bind('click', Popup.printIt);
        },
        
        printIt : function () {
            var win = window.open("","Print");
            if (win.document) {
                win.document.writeln('<img src="'+ $(this).attr('href') +'" alt="image" />');
                win.document.close();
                win.focus();
                win.print();
            }
            
            return false;
            }
    };
        $(document).ready(function () {
        Popup.init();
    });
    
    $('#btn_submit').click(function(){
        var btn = $(this);
        btn.button('loading');
        setTimeout(function(){
            btn.button('reset')
        }, 2000);
    });
    
    $('.btn-close-case').click(function(){
        var id = $(this).attr("id");
        $("#id-close").attr({href: id});
    });
    
    $('.btn-delete-case').click(function(){
        var id = $(this).attr("id");
        $("#id-delete").attr({href: id});
    });

   $('.favorite').click(function(){
        var id = $(this).attr("id");
        var rel = $(this).attr("rel");
        $.ajax({
            type: "GET",
            url: id,
            success: function(data){
                if (data == "true"){
                    $(".star"+rel).addClass('btn-warning');
                }else{
                    $(".star"+rel).removeClass('btn-warning');
                }
            },
            error: function (request) {
                alert(request.responseText);
            }
        });
    });
    
});

function internetStatus(){
    var status = navigator.onLine ? 'online' : 'offline';
    if (status == 'offline'){
        alert("To use the map feature you need to be connected to internet.");
    }else{
        $('#map_canvas').fadeIn();
        loadScript();
    }
};

function loadScript() {
    var script = document.createElement("script");
    script.type = "text/javascript";
    script.src = "http://maps.google.com/maps/api/js?sensor=false&callback=initialize";
    document.body.appendChild(script);
}