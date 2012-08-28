// jslint configuration.  Don't put spaces before 'jslint' and 'global'.
/*jslint browser: true */
/*global $, window */

// Format the form.
$(document).ready(function () {
  $('div#content').addClass('container')
  $('form p').wrap('<div class="row" />')
  $('form p label').wrap('<div class="span4 offset1" />')
  $('form p input[type="text"]').wrap('<div class="span4" />')
  $('form input[type="submit"]').wrap('<div class="span4" />')
  $('form li label').wrap('<div class="span8 offset1" />')
})

