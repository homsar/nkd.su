$(document).ready(function(){
  // django shenanigans
  function csrfSafeMethod(method) {
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
  }

  var csrftoken = $.cookie('csrftoken');

  $.ajaxSetup({
    crossDomain: false,
    beforeSend: function(xhr, settings) {
      if (!csrfSafeMethod(settings.type)) {
          xhr.setRequestHeader("X-CSRFToken", csrftoken);
      }
    }
  });

  // stick to bottom of screen
  function stick() {
    if (($('div#selection').offset().top < ($(window).scrollTop() + $(window).height() - $('div#stuck').height())) == ($('div#stick').hasClass('invisible'))) {
      $('div#stick').toggleClass('invisible');
      // compensate to prevent document height changing
      if ($('div#stick').hasClass('invisible')) {
        $('div#selection').css('margin-top', $('div#stuck').height()+'px');
      } else {
        $('div#selection').css('margin-top', 0);
      }
    }
  }

  // selection representation 
  function update_selection(data) {
    // update document
    $("div#selection").html(data);
    stick();

    // build a list of IDs of selected tracks
    var selected_tracks = [];
    $('p.id').each(function() {
      selected_tracks.push($(this).text())
    });
    
    // ensure selected tracks are marked as such and vice-versa
    $("div.track").each(function() {
      // if the selected_tracks doesn't match one of our selection statuses...
      if (($.inArray(this.id, selected_tracks) != -1) != $(this).hasClass('selected')) {
        $(this).toggleClass('selected');
      }
      $(this).removeClass('pending');
    });

    // enable select all button
    $("a.select_all").click(function(event) {
      event.preventDefault();
      var all_selectable = [];
      $('div.track.selectable').each(function() {
        all_selectable.push(this.id);
        $(this).addClass('pending');
      });
      var id_map = { track_id: all_selectable }
      $.post($(this).attr('href'), id_map, function(data) {
        update_selection(data);
      });
    });

    // do js-friendly actions without reloading if possible
    $("a.track_jspost").click(function(event) {
      event.preventDefault();
      var id_map = { track_id: $(this).closest('div.minitrack').find('p.id').text() }
      $.post($(this).attr('href'), id_map, function(data) {
        update_selection(data);
      });
    });

    $("a.selection_jspost").click(function(event) {
      event.preventDefault();
      $.post($(this).attr('href'), function(data) {
        update_selection(data);
      });
    });

    // make div#stick.invisible
    $(window).scroll(function() {
      stick();
    });

    // scroll to bottom when asked
    $('div#stick.invisible div#stuck h3').on("click", function() {
      window.scrollTo(0,$('div#selection').offset().top);
    });
    
  };

  $.post('/do/selection/', function(data) {
    update_selection(data);
  });

  // toggling selection
  $("div.track.selectable").on("click", function(event) {
    if (!$(event.target).is('a')) {
      $(this).addClass('pending');
      var id_map = { track_id: this.id };
      if (!$(this).hasClass("selected")) {
        $.post('/do/select/', id_map, function(data) {
          update_selection(data);
        });
      }
      else {
        $.post('/do/deselect/', id_map, function(data) {
          update_selection(data);
        });
      }
    }
  });
});
